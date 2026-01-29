// Base API configuration
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Document types
export interface Document {
  document_id: string;
  file_name: string;
  mime_type: string;
  created_at: string;
  chunk_count: number;
}

export interface DocumentDetail extends Document {
  meta: Record<string, unknown>;
  chunks: Chunk[];
}

// Chunk types
export interface Chunk {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  meta: Record<string, unknown>;
  created_at: string;
  file_name?: string;
  collection_id?: string;
  source?: string;
}

// API response types
export interface PaginatedResponse<T> {
  items: T[];
}

export interface DocumentListResponse extends PaginatedResponse<Document> { }
export interface ChunkListResponse extends PaginatedResponse<Chunk> { }
export interface DocumentChunksResponse {
  document_id: string;
  file_name: string;
  chunks: Chunk[];
}

// Upload types
export interface UploadResponse {
  doc_id: string;
  filename: string;
  collection: string;
  status: string;
  chunks_count: number;
  chunk_config: {
    chunk_chars: number;
    overlap_chars: number;
  };
  embeddings_provider: string;
}

export interface UploadArgs {
  file: File;
  collectionId?: string;
  chunkChars?: number;
  overlapChars?: number;
  embedderProvider?: "hash" | "sentence-transformers";
}

// Generic API request function
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API request failed: ${response.status} - ${errorText}`);
  }

  return response.json();
}

// Document API functions
export async function getDocuments(
  collectionId: string = "default",
  limit: number = 10,
  offset: number = 0
): Promise<DocumentListResponse> {
  const params = new URLSearchParams({
    collection_id: collectionId,
    limit: limit.toString(),
    offset: offset.toString(),
  });

  return apiRequest<DocumentListResponse>(`/documents?${params}`);
}

export async function getDocument(
  documentId: string,
  collectionId: string = "default"
): Promise<DocumentDetail> {
  const params = new URLSearchParams({ collection_id: collectionId });
  return apiRequest<DocumentDetail>(`/documents/${documentId}?${params}`);
}

export async function deleteDocument(
  documentId: string,
  collectionId: string = "default"
): Promise<{ message: string; document_id: string }> {
  const params = new URLSearchParams({ collection_id: collectionId });

  return apiRequest<{ message: string; document_id: string }>(
    `/documents/${documentId}?${params}`,
    { method: 'DELETE' }
  );
}

// Chunk API functions
export async function getChunks(
  collectionId: string = "default",
  limit: number = 10,
  offset: number = 0,
  documentId?: string
): Promise<ChunkListResponse> {
  const params = new URLSearchParams({
    collection_id: collectionId,
    limit: limit.toString(),
    offset: offset.toString(),
    ...(documentId && { document_id: documentId }),
  });

  return apiRequest<ChunkListResponse>(`/chunks?${params}`);
}

export async function getChunk(
  chunkId: string,
  collectionId: string = "default"
): Promise<Chunk> {
  const params = new URLSearchParams({ collection_id: collectionId });
  return apiRequest<Chunk>(`/chunks/${chunkId}?${params}`);
}

export async function getDocumentChunks(
  documentId: string,
  collectionId: string = "default",
  limit: number = 100,
  offset: number = 0
): Promise<DocumentChunksResponse> {
  const params = new URLSearchParams({
    collection_id: collectionId,
    limit: limit.toString(),
    offset: offset.toString(),
  });

  return apiRequest<DocumentChunksResponse>(`/documents/${documentId}/chunks?${params}`);
}

// Upload API function (re-exports from upload.ts)
export { uploadFile } from './upload';
export type { UploadArgs, UploadResponse } from './upload';

// Health check
export async function healthCheck(): Promise<{ status: string }> {
  return apiRequest<{ status: string }>('/health');
}
