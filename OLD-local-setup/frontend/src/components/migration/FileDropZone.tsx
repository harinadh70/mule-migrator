import { useState, useCallback, useRef } from "react";
import { Upload, FileCode2, X, FolderOpen, Archive, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { uploadMigrationZip } from "@/api/migrations";
import type { UploadSummary } from "@/api/migrations";

interface UploadedFile {
  name: string;
  content: string;
  size: number;
  path: string; // relative path from folder
}

interface FileDropZoneProps {
  onFilesLoaded: (xml: string, files: UploadedFile[]) => void;
  files: UploadedFile[];
  /** Called when a ZIP upload completes and a migration is created server-side */
  onZipMigrationCreated?: (migrationId: string, summary: UploadSummary) => void;
  /** Settings for ZIP upload */
  groupId?: string;
  javaVersion?: string;
  aiEnhancement?: boolean;
}

// File extensions to pick up from a MuleSoft project folder
const SUPPORTED_EXTENSIONS = [
  ".xml", ".raml", ".yaml", ".yml", ".json", ".properties",
  ".dwl", ".wsdl", ".xsd", ".mflow", ".mxml",
];

function isSupported(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

// Recursively read all files from a dropped folder via DataTransferItem
async function readDirectoryEntries(
  entry: FileSystemDirectoryEntry
): Promise<FileSystemEntry[]> {
  return new Promise((resolve) => {
    const reader = entry.createReader();
    const allEntries: FileSystemEntry[] = [];
    const readBatch = () => {
      reader.readEntries((entries) => {
        if (entries.length === 0) {
          resolve(allEntries);
        } else {
          allEntries.push(...entries);
          readBatch(); // keep reading until empty
        }
      });
    };
    readBatch();
  });
}

async function readFileEntry(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => {
    entry.file(resolve, reject);
  });
}

async function traverseDirectory(
  entry: FileSystemEntry,
  basePath: string = ""
): Promise<{ file: File; path: string }[]> {
  const results: { file: File; path: string }[] = [];

  if (entry.isFile) {
    const fileEntry = entry as FileSystemFileEntry;
    if (isSupported(entry.name)) {
      const file = await readFileEntry(fileEntry);
      results.push({ file, path: basePath ? `${basePath}/${entry.name}` : entry.name });
    }
  } else if (entry.isDirectory) {
    const dirEntry = entry as FileSystemDirectoryEntry;
    const children = await readDirectoryEntries(dirEntry);
    const subPath = basePath ? `${basePath}/${entry.name}` : entry.name;
    for (const child of children) {
      // Skip common non-source directories
      if (child.name === "target" || child.name === "node_modules" || child.name === ".git" || child.name === ".mule" || child.name === "__MACOSX") {
        continue;
      }
      const childResults = await traverseDirectory(child, subPath);
      results.push(...childResults);
    }
  }
  return results;
}

export default function FileDropZone({
  onFilesLoaded,
  files,
  onZipMigrationCreated,
  groupId,
  javaVersion,
  aiEnhancement,
}: FileDropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  // ZIP upload state
  const [zipUploadProgress, setZipUploadProgress] = useState(0);
  const [zipUploadStatus, setZipUploadStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [zipUploadMessage, setZipUploadMessage] = useState("");
  const [zipSummary, setZipSummary] = useState<UploadSummary | null>(null);

  // Handle ZIP file upload to backend
  const handleZipUpload = useCallback(
    async (file: File) => {
      // Validate size client-side (50MB)
      if (file.size > 50 * 1024 * 1024) {
        setZipUploadStatus("error");
        setZipUploadMessage("ZIP file exceeds 50MB limit.");
        return;
      }

      setZipUploadStatus("uploading");
      setZipUploadProgress(0);
      setZipUploadMessage(`Uploading ${file.name}...`);
      setZipSummary(null);

      try {
        const result = await uploadMigrationZip(
          file,
          undefined, // project_name defaults to filename
          groupId,
          javaVersion,
          aiEnhancement,
          (progress) => setZipUploadProgress(progress)
        );

        const summary = result.upload_summary;
        if (summary) {
          setZipSummary(summary);
          setZipUploadMessage(
            `Found ${summary.xml_files_found} XML file${summary.xml_files_found !== 1 ? "s" : ""}` +
            (summary.config_files_found > 0 ? ` and ${summary.config_files_found} config file${summary.config_files_found !== 1 ? "s" : ""}` : "") +
            ` in project`
          );
        }

        setZipUploadStatus("success");
        setZipUploadProgress(100);

        if (onZipMigrationCreated && summary) {
          onZipMigrationCreated(result.id, summary);
        }
      } catch (err: any) {
        setZipUploadStatus("error");
        const detail = err?.response?.data?.detail || err?.message || "Upload failed";
        setZipUploadMessage(detail);
        setZipUploadProgress(0);
      }
    },
    [groupId, javaVersion, aiEnhancement, onZipMigrationCreated]
  );

  const processFiles = useCallback(
    async (newEntries: { file: File; path: string }[]) => {
      const newFiles: UploadedFile[] = [...files];

      for (const { file, path } of newEntries) {
        try {
          const content = await file.text();
          if (!newFiles.some((f) => f.path === path)) {
            newFiles.push({
              name: file.name,
              content,
              size: file.size,
              path,
            });
          }
        } catch {
          // Skip unreadable files
        }
      }

      const combined = newFiles.map((f) => `<!-- ${f.path} -->\n${f.content}`).join("\n\n");
      onFilesLoaded(combined, newFiles);
    },
    [files, onFilesLoaded]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      // Check if any dropped file is a ZIP
      const droppedFiles = Array.from(e.dataTransfer.files);
      const zipFile = droppedFiles.find(
        (f) => f.name.toLowerCase().endsWith(".zip") || f.type === "application/zip"
      );

      if (zipFile) {
        await handleZipUpload(zipFile);
        return;
      }

      // Otherwise handle as folder / individual files
      setIsProcessing(true);
      try {
        const items = e.dataTransfer.items;
        const allEntries: { file: File; path: string }[] = [];

        // Use webkitGetAsEntry for folder support
        for (let i = 0; i < items.length; i++) {
          const entry = items[i].webkitGetAsEntry?.();
          if (entry) {
            const results = await traverseDirectory(entry);
            allEntries.push(...results);
          }
        }

        // Fallback to regular files if no entries found
        if (allEntries.length === 0 && e.dataTransfer.files.length > 0) {
          for (const file of droppedFiles) {
            if (isSupported(file.name)) {
              allEntries.push({ file, path: file.name });
            }
          }
        }

        await processFiles(allEntries);
      } finally {
        setIsProcessing(false);
      }
    },
    [processFiles, handleZipUpload]
  );

  const handleFileInput = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files || e.target.files.length === 0) return;
      setIsProcessing(true);
      try {
        const entries: { file: File; path: string }[] = [];
        for (const file of Array.from(e.target.files)) {
          if (isSupported(file.name)) {
            // webkitRelativePath gives folder structure
            const path = (file as any).webkitRelativePath || file.name;
            entries.push({ file, path });
          }
        }
        await processFiles(entries);
      } finally {
        setIsProcessing(false);
        e.target.value = ""; // reset input
      }
    },
    [processFiles]
  );

  const handleZipInput = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files || e.target.files.length === 0) return;
      const file = e.target.files[0];
      await handleZipUpload(file);
      e.target.value = "";
    },
    [handleZipUpload]
  );

  const removeFile = useCallback(
    (path: string) => {
      const remaining = files.filter((f) => f.path !== path);
      const combined = remaining.map((f) => `<!-- ${f.path} -->\n${f.content}`).join("\n\n");
      onFilesLoaded(combined, remaining);
    },
    [files, onFilesLoaded]
  );

  const clearAll = useCallback(() => {
    onFilesLoaded("", []);
    setZipUploadStatus("idle");
    setZipUploadProgress(0);
    setZipUploadMessage("");
    setZipSummary(null);
  }, [onFilesLoaded]);

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const xmlCount = files.filter((f) => f.name.endsWith(".xml")).length;
  const otherCount = files.length - xmlCount;

  return (
    <div className="space-y-3">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative rounded-lg border-2 border-dashed p-6 text-center transition-all ${
          isDragging
            ? "border-[#0070AD] bg-[#0070AD]/5 scale-[1.01]"
            : "border-gray-300 dark:border-white/[0.12] hover:border-[#0070AD]/50"
        }`}
      >
        {isProcessing ? (
          <div className="flex flex-col items-center gap-2">
            <div className="h-8 w-8 border-2 border-[#0070AD] border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-[#0070AD] font-medium">Reading files...</p>
          </div>
        ) : zipUploadStatus === "uploading" ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 text-[#0070AD] animate-spin" />
            <p className="text-sm text-[#0070AD] font-medium">{zipUploadMessage}</p>
            {/* Progress bar */}
            <div className="w-full max-w-xs mx-auto">
              <div className="h-2 rounded-full bg-gray-200 dark:bg-white/[0.08] overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#0070AD] to-[#1B365D] transition-all duration-300 ease-out"
                  style={{ width: `${zipUploadProgress}%` }}
                />
              </div>
              <p className="text-xs text-capText-light dark:text-gray-500 mt-1">{zipUploadProgress}%</p>
            </div>
          </div>
        ) : (
          <>
            <Upload
              className={`mx-auto h-8 w-8 mb-2 transition-colors ${
                isDragging ? "text-[#0070AD]" : "text-gray-400 dark:text-gray-500"
              }`}
            />
            <p className="text-sm font-medium text-capText dark:text-white">
              {isDragging ? "Drop files or folder here" : "Drag & drop MuleSoft project"}
            </p>
            <p className="text-xs text-capText-light dark:text-gray-500 mt-1">
              ZIP archives, project folders, or individual XML files
            </p>
            <div className="flex items-center justify-center gap-3 mt-3">
              <button
                type="button"
                onClick={() => zipInputRef.current?.click()}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-[#0070AD] text-white hover:bg-[#005A8A] transition-colors flex items-center gap-1.5"
              >
                <Archive className="h-3.5 w-3.5" />
                Upload ZIP
              </button>
              <button
                type="button"
                onClick={() => folderInputRef.current?.click()}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-[#0070AD]/30 dark:border-white/[0.15] text-[#0070AD] dark:text-gray-300 hover:bg-[#0070AD]/5 dark:hover:bg-white/[0.03] transition-colors flex items-center gap-1.5"
              >
                <FolderOpen className="h-3.5 w-3.5" />
                Upload Folder
              </button>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-gray-300 dark:border-white/[0.15] text-capText dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/[0.03] transition-colors flex items-center gap-1.5"
              >
                <FileCode2 className="h-3.5 w-3.5" />
                Select Files
              </button>
            </div>
          </>
        )}

        {/* Hidden inputs */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".xml,.raml,.yaml,.yml,.json,.properties,.dwl,.wsdl,.xsd"
          onChange={handleFileInput}
          className="hidden"
        />
        <input
          ref={folderInputRef}
          type="file"
          // @ts-ignore - webkitdirectory is not in React types
          webkitdirectory=""
          // @ts-ignore
          directory=""
          multiple
          onChange={handleFileInput}
          className="hidden"
        />
        <input
          ref={zipInputRef}
          type="file"
          accept=".zip,application/zip"
          onChange={handleZipInput}
          className="hidden"
        />
      </div>

      {/* ZIP Upload Status Banner */}
      {zipUploadStatus === "success" && zipSummary && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-800/30">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">
              {zipUploadMessage}
            </p>
            {zipSummary.xml_file_names.length > 0 && (
              <div className="mt-2 space-y-1">
                {zipSummary.xml_file_names.map((name) => (
                  <div key={name} className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-400">
                    <FileCode2 className="h-3 w-3 flex-shrink-0" />
                    <span className="truncate font-mono">{name}</span>
                  </div>
                ))}
                {zipSummary.config_file_names.map((name) => (
                  <div key={name} className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-500">
                    <FileCode2 className="h-3 w-3 flex-shrink-0 opacity-60" />
                    <span className="truncate font-mono opacity-75">{name}</span>
                  </div>
                ))}
              </div>
            )}
            {zipSummary.project_root && (
              <p className="text-xs text-emerald-600 dark:text-emerald-500 mt-1.5">
                Project root: <span className="font-mono">{zipSummary.project_root || "/"}</span>
              </p>
            )}
          </div>
          <button
            onClick={clearAll}
            className="p-1 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/30 text-emerald-500 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {zipUploadStatus === "error" && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800/30">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800 dark:text-red-300">Upload Failed</p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{zipUploadMessage}</p>
          </div>
          <button
            onClick={() => { setZipUploadStatus("idle"); setZipUploadMessage(""); }}
            className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* File List (for individual / folder uploads) */}
      {files.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
              {files.length} file{files.length !== 1 ? "s" : ""} •{" "}
              {xmlCount} XML{otherCount > 0 ? `, ${otherCount} other` : ""} •{" "}
              {formatSize(totalSize)}
            </p>
            <button
              onClick={clearAll}
              className="text-xs text-red-500 hover:text-red-600 font-medium"
            >
              Clear all
            </button>
          </div>
          <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
            {files.map((file) => (
              <div
                key={file.path}
                className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.06]"
              >
                <FileCode2 className="h-4 w-4 text-[#0070AD] flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-capText dark:text-white truncate">
                    {file.path}
                  </p>
                  <p className="text-xs text-capText-light dark:text-gray-500">
                    {formatSize(file.size)}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(file.path);
                  }}
                  className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
