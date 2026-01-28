"use client"

import { useState } from "react";
import { uploadFile, UploadResponse } from "@/lib/upload";

export default function UploadPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [collectionId, setCollectionId] = useState('default');
  const [embedderProvider, setEmbedderProvider] = useState<"hash" | "sentence-transformers">('hash');

  async function onUpload() {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const r = await uploadFile(apiUrl, {
        file: file,
        collectionId: collectionId,
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
        <input name="file"
          type="file" onChange={e => setFile(e.target.files ? e.target.files[0] : null)} style={{}} />
        <button 
          onClick={onUpload} 
          disabled={!file || uploading} 
          style={{ 
            marginLeft: 12, 
            padding: "8px 16px", 
            borderRadius: 8, 
            border: "1px solid #0070f3", 
            background: (!file || uploading) ? "#ccc" : "#0070f3", 
            color: "#fff", 
            cursor: (!file || uploading) ? "not-allowed" : "pointer",
            opacity: (!file || uploading) ? 0.6 : 1
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

      {result && (
        <pre style={{ marginTop: 24, maxWidth: 700, margin: "24px auto", padding: 16, background: "#f0f0f0", borderRadius: 8, overflowX: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </main>
  );

}
