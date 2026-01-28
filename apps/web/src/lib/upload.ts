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

export async function uploadFile(apiUrl: string, args: UploadArgs): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append('file', args.file);
  fd.append('collection', args.collectionId ?? 'default');
  fd.append('chunk_chars', String(args.chunkChars ?? 2000));
  fd.append('overlap_chars', String(args.overlapChars ?? 200));
  fd.append('embeddings', args.embedderProvider ?? 'hash');
  
  console.log('Uploading file with params:', {
    collection: args.collectionId ?? 'default',
    chunk_chars: args.chunkChars ?? 2000,
    overlap_chars: args.overlapChars ?? 200,
    embeddings: args.embedderProvider ?? 'hash',
  });

  const response = await fetch(`${apiUrl}/upload`, {
    method: 'POST',
    body: fd,
  })

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Upload failed: HTTP ${response.status} - ${errorText}`);
  }

  return response.json();
}
