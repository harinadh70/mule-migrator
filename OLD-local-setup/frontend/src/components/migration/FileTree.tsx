import { useState, useMemo } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  File as FileIcon,
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

function getFileIcon(name: string) {
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
}: {
  node: TreeNode;
  depth: number;
  selectedFile: MigrationFile | null;
  onSelectFile: (file: MigrationFile) => void;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const isSelected = selectedFile?.path === node.file?.path;

  if (node.isDirectory) {
    return (
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
          )}
          {expanded ? (
            <FolderOpen className="h-4 w-4 flex-shrink-0 text-amber-500" />
          ) : (
            <Folder className="h-4 w-4 flex-shrink-0 text-amber-500" />
          )}
          <span className="truncate font-medium">{node.name}</span>
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
                defaultExpanded={depth < 2}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const Icon = getFileIcon(node.name);

  return (
    <button
      onClick={() => node.file && onSelectFile(node.file)}
      className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm transition-colors ${
        isSelected
          ? "bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300"
          : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
      }`}
      style={{ paddingLeft: `${depth * 16 + 24}px` }}
    >
      <Icon className="h-4 w-4 flex-shrink-0" />
      <span className="truncate">{node.name}</span>
    </button>
  );
}

export default function FileTree({
  files,
  selectedFile,
  onSelectFile,
}: FileTreeProps) {
  const tree = useMemo(() => buildTree(files), [files]);

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
    <div className="overflow-y-auto py-2">
      {tree.map((node) => (
        <TreeNodeItem
          key={node.path}
          node={node}
          depth={0}
          selectedFile={selectedFile}
          onSelectFile={onSelectFile}
          defaultExpanded={true}
        />
      ))}
    </div>
  );
}
