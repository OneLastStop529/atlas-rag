"use client";

import { useState, useEffect } from "react";
import {
  uploadFile,
  UploadResponse,
  getDocuments,
  Document,
  DocumentListResponse,
} from "@/lib/api";
import { UploadFieldErrors, UploadRequestError } from "@/lib/upload";
import {
  EMBEDDINGS_PROVIDER_OPTIONS,
  EmbeddingsProviderId,
} from "@/lib/embeddings";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [collectionId, setCollectionId] = useState("default");
  const [embeddingsProvider, setEmbeddingsProvider] =
    useState<EmbeddingsProviderId>("sentence-transformers");
  const [chunkChars, setChunkChars] = useState(700);
  const [overlapChars, setOverlapChars] = useState(Math.ceil(chunkChars * 0.14));
  const [docs, setDocs] = useState<DocumentListResponse>({ items: [] });
  const [docsErr, setDocsErr] = useState<Error | null>(null);
  const [fieldErrors, setFieldErrors] = useState<UploadFieldErrors>({});

  const chunkConfigError =
    chunkChars <= 0
      ? "Chunk size must be greater than 0."
      : overlapChars < 0
        ? "Overlap must be 0 or greater."
        : overlapChars >= chunkChars
          ? "Overlap must be less than chunk size."
          : null;

  useEffect(() => {
    let cancelled = false;
    setDocsErr(null);

    getDocuments()
      .then((fetchedDocs) => {
        if (!cancelled) {
          setDocs(fetchedDocs);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDocsErr(err instanceof Error ? err : new Error("Failed to fetch documents"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [result]);

  async function onUpload() {
    if (!file) return;
    setUploading(true);
    setResult(null);
    setFieldErrors({});
    setError(null);
    try {
      const r = await uploadFile({
        file,
        collectionId,
        chunkChars,
        overlapChars,
        embeddingsProvider,
      });
      setResult(r);
    } catch (err) {
      if (err instanceof UploadRequestError) {
        setFieldErrors(err.fields);
        setError(err.message);
      } else {
        const errorMessage = err instanceof Error ? err.message : "Upload failed";
        setError(errorMessage);
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="atlas-page">
      <header className="atlas-hero">
        <h1>Document Upload</h1>
        <p>Configure chunking and embeddings, then ingest files into your collection.</p>
      </header>

      <section className="atlas-card">
        <div className="atlas-grid">
          <label className="atlas-field">
            <span>Collection</span>
            <input
              name="collectionId"
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value)}
            />
          </label>

          <label className="atlas-field">
            <span>Embeddings Provider</span>
            <select
              name="embeddingsProvider"
              value={embeddingsProvider}
              onChange={(e) => {
                setEmbeddingsProvider(e.target.value as EmbeddingsProviderId);
                setFieldErrors((prev) => {
                  const next = { ...prev };
                  delete next.embeddings_provider;
                  return next;
                });
              }}
            >
              {EMBEDDINGS_PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {fieldErrors.embeddings_provider && (
              <div className="atlas-error">{fieldErrors.embeddings_provider}</div>
            )}
          </label>

          <label className="atlas-field">
            <span>Chunk Size (characters)</span>
            <input
              name="chunkChars"
              type="number"
              min={1}
              step={100}
              value={chunkChars}
              onChange={(e) => {
                setChunkChars(Number(e.target.value));
                setFieldErrors((prev) => {
                  const next = { ...prev };
                  delete next.chunk_chars;
                  delete next.chunkChars;
                  return next;
                });
              }}
            />
            <small className="atlas-muted">Larger chunks preserve more context, but can reduce retrieval precision.</small>
            {(fieldErrors.chunk_chars || fieldErrors.chunkChars) && (
              <div className="atlas-error">{fieldErrors.chunk_chars || fieldErrors.chunkChars}</div>
            )}
          </label>

          <label className="atlas-field">
            <span>Chunk Overlap (characters)</span>
            <input
              name="overlapChars"
              type="number"
              min={0}
              step={50}
              value={overlapChars}
              onChange={(e) => {
                setOverlapChars(Number(e.target.value));
                setFieldErrors((prev) => {
                  const next = { ...prev };
                  delete next.overlap_chars;
                  delete next.overlapChars;
                  return next;
                });
              }}
            />
            <small className="atlas-muted">Overlap helps continuity across chunk boundaries, but increases redundancy.</small>
            {(fieldErrors.overlap_chars || fieldErrors.overlapChars) && (
              <div className="atlas-error">{fieldErrors.overlap_chars || fieldErrors.overlapChars}</div>
            )}
          </label>
        </div>

        {chunkConfigError && (
          <div className="atlas-warn">
            <strong>Chunk config error:</strong> {chunkConfigError}
          </div>
        )}

        <div className="atlas-actions">
          <input
            name="file"
            type="file"
            onChange={(e) => {
              setFile(e.target.files ? e.target.files[0] : null);
              setFieldErrors((prev) => {
                const next = { ...prev };
                delete next.file;
                return next;
              });
            }}
          />
          <button
            onClick={onUpload}
            disabled={!file || uploading || !!chunkConfigError}
          >
            {uploading ? "Uploading..." : "Upload"}
          </button>
          {fieldErrors.file && <div className="atlas-error">{fieldErrors.file}</div>}
        </div>
      </section>

      {error && (
        <section className="atlas-card">
          <div className="atlas-error">
            <strong>Error:</strong> {error}
          </div>
        </section>
      )}

      <section className="atlas-card">
        <h2>Documents</h2>
        {docsErr && <p className="atlas-error">Error loading documents: {docsErr.message}</p>}
        {docs.items.length === 0 ? (
          <div className="atlas-muted">No documents yet.</div>
        ) : (
          <ul className="atlas-list">
            {docs.items.map((doc: Document) => (
              <li key={doc.document_id}>
                <strong>{doc.file_name}</strong> · {doc.chunk_count} chunks ·{" "}
                <span className="atlas-muted">{new Date(doc.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {result && (
        <section className="atlas-card">
          <h2>Upload Result</h2>
          <pre className="atlas-pre">{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
