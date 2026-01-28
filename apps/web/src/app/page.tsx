"use client";

import { useMemo, useRef, useState } from "react";
import { streamChat } from "@/lib/sse";
import { useChatSSE } from "@/hooks/useChatSSE";


export default function Page() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
  const [input, setInput] = useState("");
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
          onKeyDown={(e) => { (e.key === "Enter" ? send(input) : null) && setInput("") }}
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
                {c.source ?? "source"} {"--"}
                {c.page ? `p ${c.page}` : ""} {"--"}
                {c.chunk_index ? `chunk ${c.chunk_index}` : ""}
                <span style={{ opacity: 0.8 }}>{c.snippet ?? ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

