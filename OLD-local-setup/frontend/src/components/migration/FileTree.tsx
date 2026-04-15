import { useState, useMemo } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  File as FileIcon,
  FlaskConical,
} from "lucide-react";
import type { MigrationFile } from "@/types/migration";

interface FileTreeProps {
  files: MigrationFile[];
  selectedFile: MigrationFile | null;
  onSelectFile: (file: MigrationFile) => void;
}

interface TreeNode {
  name: string;
  path: string;
  isDirectory: boolean;
  children: TreeNode[];
  file?: MigrationFile;
  isTestPath?: boolean;
}

function isTestFile(path: string): boolean {
  return path.includes("src/test/") || path.includes("Test.java") || path.includes("Tests.java") || path.includes("IT.java");
}

function buildTree(files: MigrationFile[]): TreeNode[] {
  const root: TreeNode = {
    name: "",
    path: "",
    isDirectory: true,
    children: [],
  };

  for (const file of files) {
    const parts = file.path.split("/").filter(Boolean);
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      const currentPath = parts.slice(0, i + 1).join("/");

      let child = current.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          path: currentPath,
          isDirectory: !isLast,
          children: [],
          file: isLast ? file : undefined,
          isTestPath: currentPath.includes("test"),
        };
        current.children.push(child);
      }
      current = child;
    }
  }

  // Sort: directories first, then alphabetical
  function sortNodes(nodes: TreeNode[]): TreeNode[] {
    return nodes
      .sort((a, b) => {
        if (a.isDirectory !== b.isDirectory)
          return a.isDirectory ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map((node) => ({
        ...node,
        children: sortNodes(node.children),
      }));
  }

  return sortNodes(root.children);
}

function getFileIcon(name: string, path?: string) {
  if (path && isTestFile(path)) return FlaskConical;
  if (name.endsWith(".java")) return FileCode;
  if (name.endsWith(".xml") || name.endsWith(".yaml") || name.endsWith(".yml"))
    return FileCode;
  if (name.endsWith(".md") || name.endsWith(".txt")) return FileText;
  if (name.endsWith(".properties") || name.endsWith(".json")) return FileCode;
  return FileIcon;
}

function TreeNodeItem({
  node,
  depth,
  selectedFile,
  onSelectFile,
  defaultExpanded,
  filterTestsOnly,
}: {
  node: TreeNode;
  depth: number;
  selectedFile: MigrationFile | null;
  onSelectFile: (file: MigrationFile) => void;
  defaultExpanded: boolean;
  filterTestsOnly: boolean;
}) {
  // Auto-expand test directories always, others based on depth
  const shouldExpand = defaultExpanded || node.isTestPath;
  const [expanded, setExpanded] = useState(shouldExpand);
  const isSelected = selectedFile?.path === node.file?.path;
  const isTest = node.isTestPath || (node.file && isTestFile(node.file.path));
  const folderColor = isTest ? "text-green-500" : "text-amber-500";

  if (node.isDirectory) {
    // If filtering test files only, skip non-test directories
    if (filterTestsOnly && !node.isTestPath && !node.path.includes("test")) {
      // Check if any children are test files
      const hasTestChildren = node.children.some(
        (c) => c.isTestPath || (c.file && isTestFile(c.file.path))
      );
      if (!hasTestChildren) return null;
    }

    return (
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-800 ${
            isTest ? "text-green-700 dark:text-green-400" : "text-gray-700 dark:text-gray-300"
          }`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
          )}
          {expanded ? (
            <FolderOpen className={`h-4 w-4 flex-shrink-0 ${folderColor}`} />
          ) : (
            <Folder className={`h-4 w-4 flex-shrink-0 ${folderColor}`} />
          )}
          <span className="truncate font-medium">{node.name}</span>
          {node.name === "test" && (
            <span className="ml-auto flex items-center gap-1 rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-900/30 dark:text-green-400">
              <FlaskConical className="h-3 w-3" />
              Tests
            </span>
          )}
        </button>
        {expanded && (
          <div>
            {node.children.map((child) => (
              <TreeNodeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedFile={selectedFile}
                onSelectFile={onSelectFile}
                defaultExpanded={depth < 2 || node.isTestPath === true}
                filterTestsOnly={filterTestsOnly}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // If filtering, skip non-test files
  if (filterTestsOnly && !isTest) return null;

  const Icon = getFileIcon(node.name, node.path);

  return (
    <button
      onClick={() => node.file && onSelectFile(node.file)}
      className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm transition-colors ${
        isSelected
          ? "bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300"
          : isTest
          ? "text-green-600 hover:bg-green-50 dark:text-green-400 dark:hover:bg-green-900/20"
          : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
      }`}
      style={{ paddingLeft: `${depth * 16 + 24}px` }}
    >
      <Icon className={`h-4 w-4 flex-shrink-0 ${isTest ? "text-green-500" : ""}`} />
      <span className="truncate">{node.name}</span>
    </button>
  );
}

export default function FileTree({
  files,
  selectedFile,
  onSelectFile,
}: FileTreeProps) {
  const [filterMode, setFilterMode] = useState<"all" | "tests">("all");
  const tree = useMemo(() => buildTree(files), [files]);

  const testFileCount = useMemo(
    () => files.filter((f) => isTestFile(f.path)).length,
    [files]
  );
  const sourceFileCount = files.length - testFileCount;

  if (files.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No files generated yet
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filter tabs */}
      {testFileCount > 0 && (
        <div className="flex items-center gap-1 px-3 py-2 border-b border-gray-200 dark:border-white/[0.06]">
          <button
            onClick={() => setFilterMode("all")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
              filterMode === "all"
                ? "bg-[#1B365D]/10 text-[#1B365D] dark:bg-[#0070AD]/20 dark:text-[#12ABDB]"
                : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
            }`}
          >
            <FileCode className="h-3 w-3" />
            All Files
            <span className="rounded-full bg-gray-200 px-1.5 text-[10px] dark:bg-white/10">
              {files.length}
            </span>
          </button>
          <button
            onClick={() => setFilterMode("tests")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
              filterMode === "tests"
                ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
            }`}
          >
            <FlaskConical className="h-3 w-3" />
            Test Cases
            <span className={`rounded-full px-1.5 text-[10px] ${
              filterMode === "tests"
                ? "bg-green-200 dark:bg-green-800/50"
                : "bg-gray-200 dark:bg-white/10"
            }`}>
              {testFileCount}
            </span>
          </button>
        </div>
      )}
      <div className="overflow-y-auto py-2 flex-1">
        {tree.map((node) => (
          <TreeNodeItem
            key={node.path}
            node={node}
            depth={0}
            selectedFile={selectedFile}
            onSelectFile={onSelectFile}
            defaultExpanded={true}
            filterTestsOnly={filterMode === "tests"}
          />
        ))}
      </div>
    </div>
  );
}
