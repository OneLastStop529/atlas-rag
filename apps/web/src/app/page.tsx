"use client";

import { useEffect, useRef, useState } from "react";
import { useChatSSE } from "@/hooks/useChatSSE";
import { getChunk, Chunk } from "@/lib/api";
import {
  EMBEDDINGS_PROVIDER_OPTIONS,
  EmbeddingsProviderId,
} from "@/lib/embeddings";

type HistoryItem = {
  id: string;
  question: string;
  answer: string;
  expanded: boolean;
};

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
  const [embeddingsProvider, setEmbeddingsProvider] =
    useState<EmbeddingsProviderId>("sentence-transformers");
  const [testingLlm, setTestingLlm] = useState(false);
  const [llmTestStatus, setLlmTestStatus] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [reformulations, setReformulations] = useState<string[]>([]);
  const lastHistoryKeyRef = useRef<string>("");

  async function openCitation(chunkId: string) {
    setSelected(null);
    setSelectedErr(null);
    setLoadingChunk(true);
    try {
      const detail = await getChunk(chunkId);
      setSelected(detail);
    } catch (err: unknown) {
      setSelectedErr(err instanceof Error ? err.message : "Failed to load chunk");
    } finally {
      setLoadingChunk(false);
    }
  }

  const { messages, streaming, citations, send, stop, reset } = useChatSSE({
    apiUrl,
    collectionId: "default",
    k: topK,
    embeddingsProvider,
    useReranking: advancedRetrieval,
    llmProvider,
    llmModel: llmModel || undefined,
    llmBaseUrl: llmBaseUrl || undefined,
    onReformulations: (items) => setReformulations(items),
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedProvider = window.localStorage.getItem("llm.provider");
    const storedModel = window.localStorage.getItem("llm.model");
    const storedBaseUrl = window.localStorage.getItem("llm.baseUrl");
    const storedTopK = window.localStorage.getItem("rag.topK");
    const storedEmbeddingsProvider = window.localStorage.getItem(
      "rag.embeddingsProvider"
    );
    const storedHistory = window.localStorage.getItem("rag.history");

    if (storedProvider) setLlmProvider(storedProvider);
    if (storedModel) setLlmModel(storedModel);
    if (storedBaseUrl) setLlmBaseUrl(storedBaseUrl);
    if (storedTopK) setTopK(Number(storedTopK) || 5);
    if (storedEmbeddingsProvider) {
      setEmbeddingsProvider(storedEmbeddingsProvider as EmbeddingsProviderId);
    }
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
    window.localStorage.setItem("rag.embeddingsProvider", embeddingsProvider);
  }, [llmProvider, llmModel, llmBaseUrl, topK, embeddingsProvider]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("rag.history", JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    if (streaming) return;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const lastAssistant = [...messages].reverse().find(
      (m) => m.role === "assistant"
    );
    if (!lastUser || !lastAssistant) return;

    const key = `${lastUser.content}::${lastAssistant.content}`;
    if (key === lastHistoryKeyRef.current) return;

    lastHistoryKeyRef.current = key;
    const entry: HistoryItem = {
      id: `${Date.now()}`,
      question: lastUser.content,
      answer: lastAssistant.content,
      expanded: false,
    };
    setHistory((items) => [entry, ...items].slice(0, 5));
  }, [streaming, messages]);

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
        else {
          detail = `OK: ${data?.provider || "llm"}${
            data?.sample ? ` - ${data.sample}` : ""
          }`;
        }
      } catch {
        detail = response.ok ? "OK" : `HTTP ${response.status}`;
      }

      if (!response.ok) throw new Error(detail);
      setLlmTestStatus(detail);
    } catch (err: unknown) {
      setLlmTestStatus(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTestingLlm(false);
    }
  }

  function onSend() {
    if (!input.trim()) return;
    send(input);
    setInput("");
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Atlas RAG</h1>
        <p>Ask grounded questions and inspect citations instantly.</p>
      </header>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-title-row">
            <h2>LLM Settings</h2>
            <button
              className="btn btn-secondary"
              onClick={testLlmConnection}
              disabled={testingLlm}
            >
              {testingLlm ? "Testing..." : "Test Connection"}
            </button>
          </div>
          <div className="field-grid">
            <label className="field">
              <span>Provider</span>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
              >
                <option value="ollama">ollama</option>
                <option value="openai">openai</option>
              </select>
            </label>
            <label className="field">
              <span>Model</span>
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder="e.g. llama3.1:8b"
              />
            </label>
            <label className="field">
              <span>Base URL</span>
              <input
                value={llmBaseUrl}
                onChange={(e) => setLlmBaseUrl(e.target.value)}
                placeholder="http://localhost:11434"
              />
            </label>
          </div>
          {llmTestStatus && (
            <p
              className={`status-line ${
                llmTestStatus.startsWith("OK") ? "ok" : "error"
              }`}
            >
              {llmTestStatus}
            </p>
          )}
        </section>

        <section className="panel">
          <h2>Retrieval Controls</h2>
          <div className="field-grid">
            <label className="field">
              <span>Top-k</span>
              <input
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) =>
                  setTopK(Math.max(1, Math.min(50, Number(e.target.value) || 1)))
                }
              />
            </label>
            <label className="field">
              <span>Embeddings</span>
              <select
                value={embeddingsProvider}
                onChange={(e) =>
                  setEmbeddingsProvider(e.target.value as EmbeddingsProviderId)
                }
              >
                {EMBEDDINGS_PROVIDER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field checkbox-field" title="Coming soon">
              <input
                type="checkbox"
                checked={advancedRetrieval}
                onChange={(e) => setAdvancedRetrieval(e.target.checked)}
                disabled
              />
              <span>Advanced retrieval (coming soon)</span>
            </label>
          </div>
        </section>
      </div>

      <section className="panel chat-panel">
        <div className="panel-title-row">
          <h2>Conversation</h2>
          <button
            className="btn btn-secondary"
            onClick={reset}
            disabled={streaming && messages.length === 0}
          >
            Reset
          </button>
        </div>

        <div className="message-list">
          {messages.length === 0 && (
            <div className="empty-state">Start by asking a question below.</div>
          )}
          {messages.map((msg, idx) => (
            <article key={idx} className={`msg ${msg.role}`}>
              <div className="msg-role">{msg.role}</div>
              <div className="msg-content">{msg.content}</div>
            </article>
          ))}
        </div>

        <div className="composer-row">
          <input
            id="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder="Ask a question..."
          />
          <button className="btn" onClick={onSend} disabled={streaming || !input.trim()}>
            Send
          </button>
          <button className="btn btn-secondary" onClick={stop} disabled={!streaming}>
            Stop
          </button>
        </div>
      </section>

      {advancedRetrieval && reformulations.length > 0 && (
        <section className="panel">
          <h2>Reformulations</h2>
          <ul className="simple-list">
            {reformulations.map((item, idx) => (
              <li key={`${item}-${idx}`}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {history.length > 0 && (
        <section className="panel">
          <h2>Recent Q&A</h2>
          <div className="history-list">
            {history.map((item) => (
              <article key={item.id} className="history-item">
                <strong>{item.question}</strong>
                <button
                  className="link-btn"
                  onClick={() =>
                    setHistory((items) =>
                      items.map((entry) =>
                        entry.id === item.id
                          ? { ...entry, expanded: !entry.expanded }
                          : entry
                      )
                    )
                  }
                >
                  {item.expanded ? "Hide answer" : "Show answer"}
                </button>
                {item.expanded && <p>{item.answer}</p>}
              </article>
            ))}
          </div>
        </section>
      )}

      {citations.length > 0 && (
        <section className="panel">
          <h2>Citations</h2>
          <ul className="simple-list">
            {citations.map((c, idx) => (
              <li key={idx}>
                <button
                  className="link-btn"
                  onClick={() => c.chunk_id && openCitation(c.chunk_id)}
                  disabled={!c.chunk_id || loadingChunk}
                >
                  {c.source ?? "source"}
                  {c.page ? ` · p${c.page}` : ""}
                  {c.chunk_index ? ` · chunk ${c.chunk_index}` : ""}
                </button>
                <span className="citation-snippet">{c.snippet ?? ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(loadingChunk || selected || selectedErr) && (
        <aside className="citation-drawer">
          <div className="panel-title-row">
            <h2>Citation</h2>
            <button className="btn btn-secondary" onClick={() => {
              setSelected(null);
              setSelectedErr(null);
            }}>
              Close
            </button>
          </div>

          {loadingChunk && <div>Loading…</div>}
          {selectedErr && <p className="status-line error">{selectedErr}</p>}

          {selected && (
            <>
              <div className="chunk-meta">
                <div><strong>Source:</strong> {selected.source}</div>
                <div><strong>Chunk:</strong> {selected.chunk_id}</div>
              </div>

              <pre>{selected.content}</pre>
              {selected.meta && Object.keys(selected.meta).length > 0 && (
                <pre>{JSON.stringify(selected.meta, null, 2)}</pre>
              )}
            </>
          )}
        </aside>
      )}
    </main>
  );
}
