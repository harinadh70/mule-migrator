import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Upload,
  RefreshCw,
  Trash2,
  Database,
  FileText,
  HardDrive,
  Loader2,
  Plus,
  AlertCircle,
} from "lucide-react";
import {
  getCollections,
  getCollectionStats,
  getDocuments,
  indexCollection,
  reindexCollection,
  deleteCollection,
} from "@/api/rag";
import SearchPlayground from "./SearchPlayground";
import { showToast } from "@/components/layout/Layout";
import type { Collection } from "@/types/rag";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function CollectionCard({
  collection,
  onReindex,
  onDelete,
  onView,
  isReindexing,
}: {
  collection: Collection;
  onReindex: () => void;
  onDelete: () => void;
  onView: () => void;
  isReindexing: boolean;
}) {
  const statusColors = {
    ready: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
    indexing: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  };

  return (
    <div className="card cursor-pointer hover:border-[#0070AD]/30 transition-colors" onClick={onView}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0070AD]/10 text-[#0070AD]">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white capitalize">
              {collection.name}
            </h4>
            {collection.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {collection.description}
              </p>
            )}
          </div>
        </div>
        <span className={`badge ${statusColors[collection.status]}`}>
          {collection.status === "indexing" && (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          )}
          {collection.status}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="text-center">
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            {collection.documentCount}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Documents</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            {collection.chunkSize}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Chunk Size</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {collection.embeddingModel}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Model</p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onReindex}
          disabled={isReindexing || collection.status === "indexing"}
          className="btn-secondary flex-1 text-xs"
        >
          {isReindexing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Reindex
        </button>
        <button
          onClick={onDelete}
          className="btn-ghost px-2 py-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
          title="Delete collection"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export default function KnowledgeBasePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploadCollection, setUploadCollection] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [showNewCollection, setShowNewCollection] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [viewingCategory, setViewingCategory] = useState<string | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);

  async function handleViewCollection(category: string) {
    setViewingCategory(category);
    setDocsLoading(true);
    try {
      const docs = await getDocuments(category);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }

  const { data: collections, isLoading: collectionsLoading } = useQuery({
    queryKey: ["ragCollections"],
    queryFn: getCollections,
  });

  const { data: stats } = useQuery({
    queryKey: ["ragStats"],
    queryFn: getCollectionStats,
  });

  const indexMutation = useMutation({
    mutationFn: () =>
      indexCollection(
        showNewCollection ? newCollectionName : uploadCollection,
        selectedFiles
      ),
    onSuccess: (result) => {
      showToast({
        type: "success",
        title: `Indexed ${result.indexed} documents`,
        message: `Collection: ${result.collection}`,
      });
      setSelectedFiles([]);
      setNewCollectionName("");
      setShowNewCollection(false);
      queryClient.invalidateQueries({ queryKey: ["ragCollections"] });
      queryClient.invalidateQueries({ queryKey: ["ragStats"] });
    },
    onError: () => {
      showToast({ type: "error", title: "Failed to index documents" });
    },
  });

  const reindexMutation = useMutation({
    mutationFn: (name: string) => reindexCollection(name),
    onSuccess: () => {
      showToast({ type: "success", title: "Reindex started" });
      queryClient.invalidateQueries({ queryKey: ["ragCollections"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => deleteCollection(name),
    onSuccess: () => {
      showToast({ type: "success", title: "Collection deleted" });
      queryClient.invalidateQueries({ queryKey: ["ragCollections"] });
      queryClient.invalidateQueries({ queryKey: ["ragStats"] });
    },
  });

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    setSelectedFiles(files);
  }

  function handleUpload() {
    const targetCollection = showNewCollection
      ? newCollectionName
      : uploadCollection;
    if (!targetCollection || selectedFiles.length === 0) {
      showToast({
        type: "error",
        title: "Select a collection and files to upload",
      });
      return;
    }
    indexMutation.mutate();
  }

  function handleDelete(name: string) {
    if (!confirm(`Delete collection "${name}"? This cannot be undone.`)) return;
    deleteMutation.mutate(name);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          RAG Knowledge Base
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Manage document collections that power the AI migration agents
        </p>
      </div>

      {/* Stats overview */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="card text-center">
            <FileText className="mx-auto h-6 w-6 text-brand-500" />
            <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
              {stats.totalDocuments}
            </p>
            <p className="text-xs text-gray-500">Documents</p>
          </div>
          <div className="card text-center">
            <Database className="mx-auto h-6 w-6 text-brand-500" />
            <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
              {stats.totalChunks.toLocaleString()}
            </p>
            <p className="text-xs text-gray-500">Chunks</p>
          </div>
          <div className="card text-center">
            <BookOpen className="mx-auto h-6 w-6 text-brand-500" />
            <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
              {stats.totalEmbeddings.toLocaleString()}
            </p>
            <p className="text-xs text-gray-500">Embeddings</p>
          </div>
          <div className="card text-center">
            <HardDrive className="mx-auto h-6 w-6 text-brand-500" />
            <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
              {formatBytes(stats.indexSizeBytes)}
            </p>
            <p className="text-xs text-gray-500">Index Size</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Collections */}
        <div className="space-y-4 xl:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Collections
            </h3>
          </div>

          {collectionsLoading && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card">
                  <div className="skeleton h-10 w-full" />
                  <div className="mt-4 skeleton h-20 w-full" />
                </div>
              ))}
            </div>
          )}

          {!collectionsLoading && collections?.length === 0 && (
            <div className="card py-12 text-center">
              <Database className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
              <p className="mt-3 text-gray-500 dark:text-gray-400">
                No collections yet. Upload documents to create your first
                collection.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {collections?.map((col) => (
              <CollectionCard
                key={col.id || col.name}
                collection={col}
                onReindex={() => reindexMutation.mutate(col.name)}
                onDelete={() => handleDelete(col.name)}
                onView={() => handleViewCollection(col.name)}
                isReindexing={reindexMutation.isPending}
              />
            ))}
          </div>

          {/* Document Viewer Panel */}
          {viewingCategory && (
            <div className="mt-6 card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white capitalize flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-[#0070AD]" />
                  {viewingCategory} Documents
                  <span className="text-sm font-normal text-gray-500">({documents.length})</span>
                </h3>
                <button
                  onClick={() => setViewingCategory(null)}
                  className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                >
                  ✕ Close
                </button>
              </div>

              {docsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-[#0070AD]" />
                </div>
              ) : (
                <div className="space-y-2">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="border border-gray-200 dark:border-white/[0.08] rounded-lg overflow-hidden"
                    >
                      <button
                        onClick={() => setExpandedDoc(expandedDoc === doc.id ? null : doc.id)}
                        className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-[#0070AD] flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900 dark:text-white">
                            {doc.title}
                          </span>
                        </div>
                        <span className="text-xs text-gray-400">
                          {expandedDoc === doc.id ? "▼" : "▶"}
                        </span>
                      </button>
                      {expandedDoc === doc.id && (
                        <div className="px-4 pb-4 border-t border-gray-100 dark:border-white/[0.05]">
                          <pre className="mt-3 text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono bg-gray-50 dark:bg-white/[0.02] p-3 rounded-lg max-h-96 overflow-y-auto">
                            {doc.full_content || doc.content}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Upload panel */}
        <div className="space-y-4">
          <div className="card space-y-4">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
              <Upload className="h-5 w-5 text-brand-500" />
              Upload Documents
            </h3>

            {/* Collection selector */}
            {!showNewCollection ? (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Target Collection
                </label>
                <select
                  value={uploadCollection}
                  onChange={(e) => setUploadCollection(e.target.value)}
                  className="select"
                >
                  <option value="">Select collection...</option>
                  {collections?.map((c) => (
                    <option key={c.id} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setShowNewCollection(true)}
                  className="mt-2 text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400"
                >
                  <Plus className="mr-1 inline h-3.5 w-3.5" />
                  Create new collection
                </button>
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  New Collection Name
                </label>
                <input
                  type="text"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                  placeholder="e.g., mulesoft-patterns"
                  className="input"
                />
                <button
                  onClick={() => setShowNewCollection(false)}
                  className="mt-2 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400"
                >
                  Use existing collection
                </button>
              </div>
            )}

            {/* File upload */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Files
              </label>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.md,.txt,.java,.xml,.yaml,.yml,.json"
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-sm text-gray-500 transition-colors hover:border-brand-400 hover:bg-brand-50/50 dark:border-gray-600 dark:bg-gray-800/50 dark:hover:border-brand-600"
              >
                <Upload className="h-5 w-5" />
                Click to select files
              </button>

              {selectedFiles.length > 0 && (
                <div className="mt-2 space-y-1">
                  {selectedFiles.map((file, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded bg-gray-100 px-2 py-1 text-xs dark:bg-gray-700"
                    >
                      <span className="truncate text-gray-700 dark:text-gray-300">
                        {file.name}
                      </span>
                      <span className="flex-shrink-0 text-gray-400">
                        {formatBytes(file.size)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={handleUpload}
              disabled={
                indexMutation.isPending ||
                selectedFiles.length === 0 ||
                (!uploadCollection && !newCollectionName)
              }
              className="btn-primary w-full"
            >
              {indexMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Indexing...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  Upload & Index ({selectedFiles.length} files)
                </>
              )}
            </button>

            <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
              <p className="text-xs text-blue-700 dark:text-blue-300">
                Supported formats: PDF, Markdown, Text, Java, XML, YAML, JSON.
                Files are chunked and embedded for semantic search.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Search playground */}
      <div className="card">
        <SearchPlayground collections={collections || []} />
      </div>
    </div>
  );
}
