export interface Collection {
  id: string;
  name: string;
  description?: string;
  documentCount: number;
  embeddingModel: string;
  chunkSize: number;
  chunkOverlap: number;
  status: "ready" | "indexing" | "error";
  createdAt: string;
  updatedAt: string;
}

export interface SearchResult {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  score: number;
  collection: string;
  documentId: string;
  chunkIndex: number;
}

export interface SearchQuery {
  query: string;
  collections?: string[];
  topK?: number;
  minScore?: number;
}

export interface IndexStats {
  totalDocuments: number;
  totalChunks: number;
  totalEmbeddings: number;
  indexSizeBytes: number;
  lastIndexedAt?: string;
  embeddingModel: string;
  collections: CollectionStats[];
}

export interface CollectionStats {
  name: string;
  documentCount: number;
  chunkCount: number;
  sizeBytes: number;
  lastUpdated: string;
}

export interface DocumentUpload {
  file: File;
  collection: string;
  metadata?: Record<string, string>;
}
