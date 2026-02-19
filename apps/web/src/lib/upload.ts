import { API_BASE_URL, UploadArgs, UploadResponse } from "./api";

export type UploadFieldErrors = Record<string, string>;

interface UploadErrorEnvelope {
  ok?: boolean;
  error?: {
    code?: string;
    message?: string;
    fields?: UploadFieldErrors;
  };
}

export class UploadRequestError extends Error {
  fields: UploadFieldErrors;

  constructor(message: string, fields: UploadFieldErrors = {}) {
    super(message);
    this.name = "UploadRequestError";
    this.fields = fields;
  }
}

export async function uploadFile(args: UploadArgs): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append('file', args.file);
  fd.append('collection', args.collectionId ?? 'default');
  fd.append('chunk_chars', String(args.chunkChars ?? 2000));
  fd.append('overlap_chars', String(args.overlapChars ?? 200));
  fd.append('embeddings_provider', args.embeddingsProvider ?? 'sentence-transformers');

  const url = `${API_BASE_URL}/upload`;
  
  const response = await fetch(url, {
    method: 'POST',
    body: fd,
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as UploadErrorEnvelope;
      const message =
        payload?.error?.message || `Upload failed with status ${response.status}`;
      const fields = payload?.error?.fields || {};
      throw new UploadRequestError(message, fields);
    }

    const errorText = await response.text();
    throw new UploadRequestError(
      `Upload failed: ${response.status} - ${errorText}`,
    );
  }

  return response.json();
}

// Re-export types for convenience
export type { UploadArgs, UploadResponse } from "./api";
