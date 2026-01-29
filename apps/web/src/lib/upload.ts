import { API_BASE_URL, apiRequest, UploadArgs, UploadResponse } from "./api";

export async function uploadFile(args: UploadArgs): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append('file', args.file);
  fd.append('collection', args.collectionId ?? 'default');
  fd.append('chunk_chars', String(args.chunkChars ?? 2000));
  fd.append('overlap_chars', String(args.overlapChars ?? 200));
  fd.append('embeddings', args.embedderProvider ?? 'hash');

  const url = `${API_BASE_URL}/upload`;
  
  const response = await fetch(url, {
    method: 'POST',
    body: fd,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Upload failed: ${response.status} - ${errorText}`);
  }

  return response.json();
}

// Re-export types for convenience
export type { UploadArgs, UploadResponse } from "./api";
