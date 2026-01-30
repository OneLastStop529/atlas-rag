"use client";

import { useState, useRef, useCallback } from "react";
import { SseEvent, streamChat } from "@/lib/sse";

export type ChatMessage = { role: "user" | "assistant"; content: string };
export type Citation = {
  chunk_id?: string;
  document_id?: string;
  source?: string;
  page?: number;
  chunk_index?: number;
  distance?: number;
  snippet?: string;
  metadata?: Record<string, unknown>;
};

export interface UseChatSSEOptions {
  apiUrl: string;
  collectionId?: string;
  k?: number;
  embedderProvider?: string;
  onToken?: (delta: string) => void;
  onCitation?: (citations: Citation[]) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export type StreamSSEEvent =
  | { event: 'token'; data: { delta: string } }
  | { event: 'citation'; data: { items: Citation[] } }
  | { event: 'done'; data: Record<string, unknown> }
  | { event: 'error'; data: { message: string } }
  | { event: string; data: Record<string, unknown> };



export function useChatSSE({ apiUrl, onToken, onCitation, onError, onComplete }: UseChatSSEOptions) {

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const runIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);



  const send = useCallback(async (input: string) => {
    const text = input.trim();
    if (!text || streaming) return;

    const runId = ++runIdRef.current;
    setStreaming(true);
    setCitations([]);
    setMessages((msgs) => [
      ...msgs,
      { role: "user", content: text },
      { role: "assistant", content: "" }
    ]);

    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      await streamChat(
        apiUrl,
        { messages: [...messages, { role: "user", content: text }] },
        ({ event, data }: SseEvent) => {
          if (runId !== runIdRef.current) return; // Ignore old runs

          switch (event) {
            case "token":
              const tokenData = data as { delta?: string };
              if (typeof tokenData.delta === 'string') {
                setMessages((msgs) => {
                  const lastIdx = msgs.length - 1;
                  const last = msgs[lastIdx];
                  if (!last || last.role !== "assistant") return msgs;
                  const delta = tokenData.delta;
                  const needsSpace =
                    last.content.length > 0 &&
                    !/\s$/.test(last.content) &&
                    !/^\s/.test(delta) &&
                    !/^[\]\)\.,!?;:]/.test(delta);
                  const updated = {
                    ...last,
                    content: needsSpace ? `${last.content} ${delta}` : last.content + delta
                  };
                  return [...msgs.slice(0, lastIdx), updated];
                });
                onToken?.(tokenData.delta);
              }
              break;

            case "citations":
              const citationData = data as { items?: Citation[] };
              if (Array.isArray(citationData.items)) {
                setCitations(citationData.items);
                onCitation?.(citationData.items);
              }
              break;

            case "error":
              const errorData = data as { message?: string };
              if (typeof errorData.message === 'string') {
                const error = new Error(errorData.message);
                onError?.(error);
              } else {
                onError?.(new Error("Unknown error"));
              }
              break;

            case "done":
              setStreaming(false);
              onComplete?.();
              break;
          }
        },
        abortController.signal
      );
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== 'AbortError') {
        onError?.(error);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [apiUrl, messages, streaming, onToken, onCitation, onError, onComplete]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    stop();
    setMessages([]);
    setCitations([]);
    setStreaming(false);
  }, [stop]);

  return {
    messages,
    streaming,
    citations,
    send,
    stop,
    reset
  };
}
