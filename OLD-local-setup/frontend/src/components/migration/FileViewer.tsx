import Editor from "@monaco-editor/react";
import { Download, Copy, Check, PenLine } from "lucide-react";
import { useState, useCallback, useRef, useEffect } from "react";
import type { MigrationFile, FileLanguage } from "@/types/migration";

interface FileViewerProps {
  file: MigrationFile | null;
  editable?: boolean;
  onContentChange?: (filePath: string, newContent: string) => void;
}

const LANGUAGE_MAP: Record<FileLanguage, string> = {
  java: "java",
  xml: "xml",
  yaml: "yaml",
  properties: "ini",
  sql: "sql",
  json: "json",
  markdown: "markdown",
  dockerfile: "dockerfile",
  text: "plaintext",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileViewer({ file, editable = false, onContentChange }: FileViewerProps) {
  const [copied, setCopied] = useState(false);
  const [currentContent, setCurrentContent] = useState<string>("");
  const originalContentRef = useRef<string>("");

  // Track whether the content has been modified from its original
  const isModified = currentContent !== originalContentRef.current;

  // Reset content when file changes
  useEffect(() => {
    if (file) {
      setCurrentContent(file.content);
      originalContentRef.current = file.content;
    }
  }, [file?.path, file?.content]);

  const handleCopy = useCallback(async () => {
    if (!file) return;
    await navigator.clipboard.writeText(currentContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [file, currentContent]);

  const handleDownload = useCallback(() => {
    if (!file) return;
    const blob = new Blob([currentContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.filename;
    a.click();
    URL.revokeObjectURL(url);
  }, [file, currentContent]);

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (!file || !value) return;
      setCurrentContent(value);
      onContentChange?.(file.path, value);
    },
    [file, onContentChange]
  );

  if (!file) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-gray-300 dark:border-gray-600">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Select a file from the tree to view its contents
        </p>
      </div>
    );
  }

  const monacoLang = LANGUAGE_MAP[file.language] || "plaintext";

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
      {/* File header */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center gap-2 overflow-hidden">
          <span className="truncate text-sm font-medium text-gray-700 dark:text-gray-300">
            {file.path}
          </span>
          <span className="flex-shrink-0 text-xs text-gray-400">
            {formatFileSize(file.size)}
          </span>
          <span className="badge-pending text-xs">{file.language}</span>
          {editable && (
            <span className="flex items-center gap-1 text-xs text-[#0070AD] dark:text-[#12ABDB]">
              <PenLine className="h-3 w-3" />
              Editing
            </span>
          )}
          {isModified && (
            <span className="flex-shrink-0 rounded-full bg-amber-100 dark:bg-amber-900/30 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-400">
              Modified
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="btn-ghost px-2 py-1 text-xs"
            title="Copy contents"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            onClick={handleDownload}
            className="btn-ghost px-2 py-1 text-xs"
            title="Download file"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Editor */}
      <div style={{ height: "400px" }}>
        <Editor
          height="400px"
          language={monacoLang}
          value={currentContent}
          onChange={editable ? handleEditorChange : undefined}
          theme="vs-dark"
          options={{
            readOnly: !editable,
            minimap: { enabled: true },
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "off",
            automaticLayout: true,
            tabSize: 4,
            padding: { top: 8 },
            cursorStyle: editable ? "line" : "line-thin",
            renderLineHighlight: editable ? "all" : "none",
          }}
        />
      </div>
    </div>
  );
}
