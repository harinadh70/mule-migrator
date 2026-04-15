import apiClient from "./client";
import type {
  Collection,
  SearchResult,
  SearchQuery,
  IndexStats,
} from "@/types/rag";

export async function search(query: SearchQuery): Promise<SearchResult[]> {
  const response = await apiClient.post<SearchResult[]>("/rag/search", query);
  return response.data;
}

export async function getCollections(): Promise<Collection[]> {
  try {
    const response = await apiClient.get<any>("/rag/collections");
    const data = response.data;
    if (Array.isArray(data)) return data;
    if (data && data.collections) return data.collections;
    return [];
  } catch {
    return [];
  }
}

export async function getCollectionStats(): Promise<IndexStats> {
  try {
    const response = await apiClient.get<any>("/rag/collections");
    const data = response.data;
    const collections = Array.isArray(data) ? data : data?.collections || [];
    const totalDocs = collections.reduce((sum: number, c: any) => sum + (c.documentCount || c.document_count || 0), 0);
    const totalChunks = totalDocs * 10;
    // Estimate: each chunk ≈ 12KB embedding (3072 dims × 4 bytes) + ~2KB text = ~14KB
    const estimatedIndexBytes = totalChunks * 14336;
    return {
      totalDocuments: totalDocs,
      totalChunks,
      totalEmbeddings: totalChunks,
      indexSizeBytes: estimatedIndexBytes,
      embeddingModel: "text-embedding-3-large",
      collections: collections.map((c: any) => {
        const docCount = c.documentCount || c.document_count || 0;
        const chunks = docCount * 10;
        return {
          name: c.name || c,
          documentCount: docCount,
          chunkCount: chunks,
          sizeBytes: chunks * 14336,
          lastUpdated: c.lastUpdated || c.updatedAt || c.updated_at || new Date().toISOString(),
        };
      }),
    };
  } catch {
    return {
      totalDocuments: 0,
      totalChunks: 0,
      totalEmbeddings: 0,
      indexSizeBytes: 0,
      embeddingModel: "all-MiniLM-L6-v2",
      collections: [],
    };
  }
}

export async function indexCollection(
  collectionName: string,
  files: File[]
): Promise<{ indexed: number; collection: string }> {
  const formData = new FormData();
  formData.append("collection", collectionName);
  files.forEach((file) => formData.append("files", file));

  const response = await apiClient.post("/rag/index", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300_000,
  });
  return response.data;
}

export async function getDocuments(category?: string): Promise<any[]> {
  try {
    const url = category ? `/rag/documents?category=${category}` : "/rag/documents";
    const response = await apiClient.get<any>(url);
    return response.data?.documents || [];
  } catch {
    return [];
  }
}

export async function reindexCollection(
  collectionName: string
): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.post(
    `/rag/collections/${collectionName}/reindex`
  );
  return response.data;
}

export async function deleteCollection(
  collectionName: string
): Promise<void> {
  await apiClient.delete(`/rag/collections/${collectionName}`);
}
