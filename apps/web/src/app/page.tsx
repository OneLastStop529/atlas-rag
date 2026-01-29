"use client";

import { useMemo, useRef, useState } from "react";
import { streamChat } from "@/lib/sse";
import { useChatSSE } from "@/hooks/useChatSSE";
import { getChunk, Chunk } from "@/lib/api";


export default function Page() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
  const [input, setInput] = useState("");
  const [selected, setSelected] = useState<Chunk | null>(null);
  const [selectedErr, setSelectedErr] = useState<string | null>(null);
  const [loadingChunk, setLoadingChunk] = useState(false);

  async function openCitation(chunkId: string) {
    setSelected(null);
    setSelectedErr(null);
    setLoadingChunk(true);
    try {
      const detail = await getChunk(chunkId);
      setSelected(detail);
    } catch (err: any) {
      setSelectedErr(err.message || "Failed to load chunk");
    } finally {
      setLoadingChunk(false);
    }
  }

  const { messages, streaming, citations, send, stop, reset } = useChatSSE({
    apiUrl,
    collectionId: "default",
    k: 5,
    embedderProvider: "hash",
  });


  const lastAssitant = useMemo(() => {
    const last = messages[messages.length - 1];
    return last?.role === "assistant" ? last.content : "";
  }, [messages]);






  return (
    <main style={{ maxWidth: 900, margin: "40px auto", }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>Atlas RAG</h1>

      <div style={{ border: "1pc solid #ddd", borderRadius: 12, padding: 12, minHeight: 280 }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 12, opacity: 0.6 }}>{msg.role.toUpperCase()}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
          </div>
        ))}
        {messages.length === 0 && <div style={{ opacity: 0.6 }}>Ask something...</div>}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
              setInput("");
            }
          }}
          placeholder="Ask a question..."
          style={{ flex: 1, padding: 10, borderRadius: 10, border: "1px solid #ddd" }}
        />
        <button onClick={() => { send(input); setInput("") }} disabled={streaming} style={{ padding: "10px 14px" }}>
          Send
        </button>
        <button onClick={stop} disabled={!streaming} style={{ padding: "10px 14px" }}>
          Stop
        </button>
        <button onClick={reset} disabled={streaming && messages.length === 0} style={{ padding: "10px 14px" }}>
          Reset
        </button>
      </div>
      {citations.length > 0 && (
        <section style={{ marginTop: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Citations</h2>
          <ul style={{ paddingLeft: 18 }}>
            {citations.map((c, idx) => (
              <li key={idx}>
                <button
                  onClick={() => c.chunk_id && openCitation(c.chunk_id)}
                  disabled={!c.chunk_id || loadingChunk}
                  style={{ textDecoration: "underline", color: "blue", background: "none", border: "none", padding: 0, cursor: c.chunk_id ? "pointer" : "default" }}
                >
                  {c.source ?? "source"} {"--"}
                  {c.page ? `p ${c.page}` : ""} {"--"}
                  {c.chunk_index ? `chunk ${c.chunk_index}` : ""}
                </button>
                <span style={{ opacity: 0.8 }}>{c.snippet ?? ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(loadingChunk || selected || selectedErr) && (
        <aside
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            width: 420,
            height: "100vh",
            borderLeft: "1px solid #ddd",
            background: "white",
            padding: 16,
            overflow: "auto",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>Citation</strong>
            <button onClick={() => { setSelected(null); setSelectedErr(null); }}>Close</button>
          </div>

          {loadingChunk && <div style={{ marginTop: 12 }}>Loading…</div>}
          {selectedErr && <div style={{ marginTop: 12, color: "crimson" }}>{selectedErr}</div>}

          {selected && (
            <>
              <div style={{ marginTop: 12, opacity: 0.8 }}>
                <div><strong>Source:</strong> {selected.source}</div>
                <div><strong>Chunk:</strong> {selected.chunk_id}</div>
              </div>

              <pre style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>
                {selected.content}
              </pre>

              {selected.meta && Object.keys(selected.meta).length > 0 && (
                <pre style={{ marginTop: 12, opacity: 0.8 }}>
                  {JSON.stringify(selected.meta, null, 2)}
                </pre>
              )}
            </>
          )}
        </aside>
      )}
    </main>
  );
}

