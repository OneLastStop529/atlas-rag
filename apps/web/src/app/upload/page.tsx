"use client"

import { useState, useEffect } from "react";
import { uploadFile, UploadResponse, getDocuments, Document, DocumentListResponse } from "@/lib/api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [collectionId, setCollectionId] = useState('default');
  const [embedderProvider, setEmbedderProvider] = useState<"hash" | "sentence-transformers">('hash');
  const [chunkChars, setChunkChars] = useState(2000);
  const [overlapChars, setOverlapChars] = useState(200);
  const [docs, setDocs] = useState<DocumentListResponse>({ items: [] });
  const [docsErr, setDocsErr] = useState<Error | null>(null);

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
      .then(fetchedDocs => {
        if (!cancelled) {
          setDocs(fetchedDocs);
        }
      })
      .catch(err => {
        if (!cancelled) {
          setDocsErr(err instanceof Error ? err : new Error('Failed to fetch documents'));
        }
      });
    return () => { cancelled = true; }
  }, [result]);

  async function onUpload() {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const r = await uploadFile({
        file: file,
        collectionId: collectionId,
        chunkChars: chunkChars,
        overlapChars: overlapChars,
        embedderProvider: embedderProvider,
      });
      console.log("Upload result:", r);
      setResult(r);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  }
  return (
    <main>
      <h1 style={{ maxWidth: 700, margin: "40px auto", padding: 16 }}>Upload File</h1>
      <div style={{ marginTop: 12 }}>
        <label>Collection</label>
        <input
          name="collectionId"
          value={collectionId}
          onChange={e => setCollectionId(e.target.value)}
          style={{ display: "block", width: "100%", padding: 10, borderRadius: 10, border: "1px solid #ddd" }}
        />
      </div>

      <div style={{ marginTop: 12 }}>
        <label>Embedder Provider</label>
        <select
          name="embedderProvider"
          value={embedderProvider}
          onChange={e => setEmbedderProvider(e.target.value as "hash" | "sentence-transformers")}
          style={{ display: "block", width: "100%", padding: 10, borderRadius: 10, border: "1px solid #ddd" }}
        >
          <option value="hash">Hash</option>
          <option value="sentence-transformers">Sentence Transformers</option>
        </select>
      </div>

      <div style={{ marginTop: 12 }}>
        <label>Chunk Size (characters)</label>
        <input
          name="chunkChars"
          type="number"
          min={1}
          step={100}
          value={chunkChars}
          onChange={e => setChunkChars(Number(e.target.value))}
          style={{ display: "block", width: "100%", padding: 10, borderRadius: 10, border: "1px solid #ddd" }}
        />
        <small style={{ color: "#666" }}>
          Larger chunks preserve more context, but can reduce retrieval precision.
        </small>
      </div>

      <div style={{ marginTop: 12 }}>
        <label>Chunk Overlap (characters)</label>
        <input
          name="overlapChars"
          type="number"
          min={0}
          step={50}
          value={overlapChars}
          onChange={e => setOverlapChars(Number(e.target.value))}
          style={{ display: "block", width: "100%", padding: 10, borderRadius: 10, border: "1px solid #ddd" }}
        />
        <small style={{ color: "#666" }}>
          Overlap helps continuity across chunk boundaries, but increases redundancy.
        </small>
      </div>

      {chunkConfigError && (
        <div style={{
          marginTop: 12,
          padding: 12,
          background: "#fff4e5",
          borderRadius: 8,
          border: "1px solid #ffcc80",
          color: "#8a4b00"
        }}>
          <strong>Chunk config error:</strong> {chunkConfigError}
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <input name="file"
          type="file" onChange={e => setFile(e.target.files ? e.target.files[0] : null)} style={{}} />
        <button
          onClick={onUpload}
          disabled={!file || uploading || !!chunkConfigError}
          style={{
            marginLeft: 12,
            padding: "8px 16px",
            borderRadius: 8,
            border: "1px solid #0070f3",
            background: (!file || uploading || !!chunkConfigError) ? "#ccc" : "#0070f3",
            color: "#fff",
            cursor: (!file || uploading || !!chunkConfigError) ? "not-allowed" : "pointer",
            opacity: (!file || uploading || !!chunkConfigError) ? 0.6 : 1
          }}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </div>

      {error && (
        <div style={{
          marginTop: 24,
          maxWidth: 700,
          margin: "24px auto",
          padding: 16,
          background: "#ffebee",
          borderRadius: 8,
          border: "1px solid #f44336",
          color: "#c62828"
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      <section>
        <h2>Documents</h2>
        {docsErr && <p style={{ color: "red" }}>Error loading documents: {docsErr.message}</p>}
        {docs.items.length === 0 ? (<div style={{ opacity: 0.6, }}> No documents yet</div>
        ) : (<ul style={{
          paddingLeft: 18
        }}>
          {docs.items.map((doc: Document) => (
            <li key={doc.document_id} >
              <strong>{doc.file_name}</strong> - {doc.chunk_count} chunks --{""}
              <span style={{ fontSize: 12, color: "#666" }}>
                {new Date(doc.created_at).toLocaleString()}
              </span>
            </li>))}
        </ul>)}
      </section>

      {result && (
        <pre style={{ marginTop: 24, maxWidth: 700, margin: "24px auto", padding: 16, background: "#f0f0f0", borderRadius: 8, overflowX: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </main>
  );

}
