"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { streamChat } from "@/lib/sse";
import { useChatSSE } from "@/hooks/useChatSSE";
import { getChunk, Chunk } from "@/lib/api";


export default function Page() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
  const [input, setInput] = useState("");
  const [selected, setSelected] = useState<Chunk | null>(null);
  const [selectedErr, setSelectedErr] = useState<string | null>(null);
  const [loadingChunk, setLoadingChunk] = useState(false);
  const [llmProvider, setLlmProvider] = useState("ollama");
  const [llmModel, setLlmModel] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [topK, setTopK] = useState(5);
  const [advancedRetrieval, setAdvancedRetrieval] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [llmTestStatus, setLlmTestStatus] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<{ id: string; question: string; answer: string; expanded: boolean }>>([]);
  const lastHistoryKeyRef = useRef<string>("");

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
    k: topK,
    embedderProvider: "hash",
    llmProvider,
    llmModel: llmModel || undefined,
    llmBaseUrl: llmBaseUrl || undefined,
  });


  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedProvider = window.localStorage.getItem("llm.provider");
    const storedModel = window.localStorage.getItem("llm.model");
    const storedBaseUrl = window.localStorage.getItem("llm.baseUrl");
    const storedTopK = window.localStorage.getItem("rag.topK");
    const storedHistory = window.localStorage.getItem("rag.history");
    if (storedProvider) setLlmProvider(storedProvider);
    if (storedModel) setLlmModel(storedModel);
    if (storedBaseUrl) setLlmBaseUrl(storedBaseUrl);
    if (storedTopK) setTopK(Number(storedTopK) || 5);
    if (storedHistory) {
      try {
        const parsed = JSON.parse(storedHistory);
        if (Array.isArray(parsed)) setHistory(parsed.slice(0, 5));
      } catch {
        // Ignore malformed storage
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("llm.provider", llmProvider);
    window.localStorage.setItem("llm.model", llmModel);
    window.localStorage.setItem("llm.baseUrl", llmBaseUrl);
    window.localStorage.setItem("rag.topK", String(topK));
  }, [llmProvider, llmModel, llmBaseUrl, topK]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("rag.history", JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    if (streaming) return;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    if (!lastUser || !lastAssistant) return;
    const key = `${lastUser.content}::${lastAssistant.content}`;
    if (key === lastHistoryKeyRef.current) return;
    lastHistoryKeyRef.current = key;
    const entry = {
      id: `${Date.now()}`,
      question: lastUser.content,
      answer: lastAssistant.content,
      expanded: false,
    };
    setHistory((items) => [entry, ...items].slice(0, 5));
  }, [streaming, messages]);

  const lastAssitant = useMemo(() => {
    const last = messages[messages.length - 1];
    return last?.role === "assistant" ? last.content : "";
  }, [messages]);

  async function testLlmConnection() {
    setTestingLlm(true);
    setLlmTestStatus(null);
    try {
      const response = await fetch(`${apiUrl}/api/llm/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: llmProvider,
          model: llmModel || undefined,
          base_url: llmBaseUrl || undefined,
          messages: [{ role: "user", content: "ping" }],
          max_tokens: 8,
        }),
      });

      let detail = "";
      try {
        const data = await response.json();
        if (!response.ok) detail = data?.detail || "Test failed";
        else detail = `OK: ${data?.provider || "llm"}${data?.sample ? " - " + data.sample : ""}`;
      } catch {
        if (!response.ok) detail = `HTTP ${response.status}`;
        else detail = "OK";
      }

      if (!response.ok) throw new Error(detail);
      setLlmTestStatus(detail);
    } catch (err: any) {
      setLlmTestStatus(err?.message || "Test failed");
    } finally {
      setTestingLlm(false);
    }
  }





  return (
    <main style={{ maxWidth: 900, margin: "40px auto", }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>Atlas RAG</h1>

      <section style={{ border: "1px solid #eee", borderRadius: 12, padding: 12, marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>LLM Settings</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, opacity: 0.7 }}>Provider</span>
            <select value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)} style={{ padding: 8, borderRadius: 8, border: "1px solid #ddd" }}>
              <option value="ollama">ollama</option>
              <option value="openai">openai</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 220 }}>
            <span style={{ fontSize: 12, opacity: 0.7 }}>Model</span>
            <input
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              placeholder="e.g. llama3.1:8b"
              style={{ padding: 8, borderRadius: 8, border: "1px solid #ddd" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 260 }}>
            <span style={{ fontSize: 12, opacity: 0.7 }}>Base URL</span>
            <input
              value={llmBaseUrl}
              onChange={(e) => setLlmBaseUrl(e.target.value)}
              placeholder="http://localhost:11434"
              style={{ padding: 8, borderRadius: 8, border: "1px solid #ddd" }}
            />
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, justifyContent: "flex-end" }}>
            <button onClick={testLlmConnection} disabled={testingLlm} style={{ padding: "8px 12px" }}>
              {testingLlm ? "Testing..." : "Test Connection"}
            </button>
          </div>
        </div>
        {llmTestStatus && (
          <div style={{ marginTop: 8, fontSize: 12, color: llmTestStatus.startsWith("OK") ? "green" : "crimson" }}>
            {llmTestStatus}
          </div>
        )}
      </section>

      <section style={{ border: "1px solid #eee", borderRadius: 12, padding: 12, marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Retrieval Controls</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, opacity: 0.7 }}>Top-k</span>
            <input
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
              style={{ width: 120, padding: 8, borderRadius: 8, border: "1px solid #ddd" }}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }} title="Advanced retrieval not available yet">
            <input
              type="checkbox"
              checked={advancedRetrieval}
              onChange={(e) => setAdvancedRetrieval(e.target.checked)}
              disabled
            />
            <span style={{ fontSize: 13, opacity: 0.7 }}>Advanced retrieval (coming soon)</span>
          </label>
        </div>
      </section>

      <div style={{ border: "1pc solid #ddd", borderRadius: 12, padding: 12, minHeight: 280 }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 12, opacity: 0.6 }}>{msg.role.toUpperCase()}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
          </div>
        ))}
        {messages.length === 0 && <div style={{ opacity: 0.6 }}>Ask something...</div>}
      </div>

      {history.length > 0 && (
        <section style={{ marginTop: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Recent Q&A</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {history.map((item) => (
              <div key={item.id} style={{ border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
                <div style={{ fontSize: 12, opacity: 0.7 }}>Q</div>
                <div style={{ fontWeight: 600 }}>{item.question}</div>
                <button
                  onClick={() =>
                    setHistory((items) =>
                      items.map((entry) =>
                        entry.id === item.id
                          ? { ...entry, expanded: !entry.expanded }
                          : entry
                      )
                    )
                  }
                  style={{ marginTop: 6, fontSize: 12, textDecoration: "underline", background: "none", border: "none", padding: 0, cursor: "pointer" }}
                >
                  {item.expanded ? "Hide answer" : "Show answer"}
                </button>
                {item.expanded && (
                  <div style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{item.answer}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

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
