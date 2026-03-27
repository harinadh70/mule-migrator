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
    // Estimate: each doc ~3KB text + 3072-dim embedding (12KB float32) ≈ 15KB per doc
    const estimatedSizeBytes = totalDocs * 15 * 1024;
    return {
      totalDocuments: totalDocs,
      totalChunks: totalDocs,
      totalEmbeddings: totalDocs,
      indexSizeBytes: estimatedSizeBytes,
      embeddingModel: "text-embedding-3-large (3072 dims)",
      collections: collections.map((c: any) => ({
        name: c.name || c,
        documentCount: c.documentCount || c.document_count || 0,
        chunkCount: c.documentCount || c.document_count || 0,
        sizeBytes: (c.documentCount || c.document_count || 0) * 15 * 1024,
        lastUpdated: c.lastUpdated || c.updatedAt || c.updated_at || new Date().toISOString(),
      })),
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

export async function getDocuments(category?: string, limit: number = 20, offset: number = 0): Promise<{ documents: any[]; total: number }> {
  try {
    let url = `/rag/documents?limit=${limit}&offset=${offset}`;
    if (category) url += `&category=${category}`;
    // Request without full_content to keep response small
    url += "&summary=true";
    const response = await apiClient.get<any>(url);
    return {
      documents: response.data?.documents || [],
      total: response.data?.total || 0,
    };
  } catch {
    return { documents: [], total: 0 };
  }
}

export async function getDocumentDetail(docId: string): Promise<any> {
  try {
    const response = await apiClient.get<any>(`/rag/documents/${docId}`);
    return response.data;
  } catch {
    return null;
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
  collectionName: string,
  password?: string
): Promise<void> {
  await apiClient.delete(`/rag/collections/${collectionName}`, {
    data: password ? { password } : undefined,
  });
}

export async function deleteDocument(
  documentId: string,
  password?: string
): Promise<void> {
  await apiClient.delete(`/rag/documents/${documentId}`, {
    data: password ? { password } : undefined,
  });
}

export async function seedKnowledgeBase(
  clearExisting: boolean = false
): Promise<any> {
  const response = await apiClient.post("/rag/seed", {
    clear_existing: clearExisting,
  });
  return response.data;
}

/** Fetch current user info and role from /.auth/me or /api/v2/auth/me */
export async function getAuthMe(): Promise<{
  email: string;
  name: string;
  role: "admin" | "user";
  is_admin: boolean;
}> {
  try {
    const response = await apiClient.get<any>("/auth/me");
    return response.data;
  } catch {
    return { email: "", name: "", role: "user", is_admin: false };
  }
}
