"use client";

import { useMemo, useRef, useState } from "react";
import { streamChat } from "@/lib/sse";

type Msg = { role: "user" | "assistant"; content: string };

export default function Page() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
  const runIdRef = useRef(0);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [citations, setCitations] = useState<any[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const lastAssitant = useMemo(() => {
    const last = messages[messages.length - 1];
    return last?.role === "assistant" ? last.content : "";
  }, [messages]);


  async function onSend() {
    console.log("onSend called", Date.now());
    const runId = ++runIdRef.current;
    const text = input.trim();
    console.log("Input text:", text, "Streaming:", streaming);
    if (!text || streaming) return;

    setInput("");
    setCitations([]);
    setMessages((msg) => [...msg, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setStreaming(true);

    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      await streamChat(
        apiUrl,
        { messages: [...messages, { role: "user", content: text }] },
        ({ event, data }) => {
          console.log("Received event:", event, data);
          if (runId !== runIdRef.current) return; // ignore old runs
          if (event === "token") {
            setMessages((msgs) => {
              const lastIdx = msgs.length - 1;
              const last = msgs[lastIdx];
              if (!last || last.role !== "assistant") return msgs;
              const updated = { ...last, content: last.content + data.delta };
              return [...msgs.slice(0, lastIdx), updated];
            });
          } else if (event === "citations") {
            setCitations(data.items ?? []);
          } else if (event === "error") {
            console.log(data)
          }
        },
        abortController.signal
      );
    } catch (err: any) {
      if (err?.name !== 'AbortError') console.error(err);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function onStop() {
    abortRef.current?.abort();
  }


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
          onKeyDown={(e) => { (e.key === "Enter" ? onSend() : null) }}
          placeholder="Ask a question..."
          style={{ flex: 1, padding: 10, borderRadius: 10, border: "1px solid #ddd" }}
        />
        <button onClick={onSend} disabled={streaming} style={{ padding: "10px 14px" }}>
          Send
        </button>
        <button onClick={onStop} disabled={!streaming} style={{ padding: "10px 14px" }}>
          Stop
        </button>
      </div>
      {citations.length > 0 && (
        <section style={{ marginTop: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Citations</h2>
          <ul style={{ paddingLeft: 18 }}>
            {citations.map((c, idx) => (
              <li key={idx}>
                {c.source ?? c.filename ?? "source"} {c.page ? `p ${c.page}` : ""} --{" "}
                <span style={{ opacity: 0.8 }}>{c.snippet ?? ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

