"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api/client";
import { DashboardHeader } from "@/components/dashboard-header";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: { index: number; filename: string; page_number: number }[];
  feedback?: "up" | "down";
}

const SUGGESTIONS = [
  "Summarize my documents",
  "What entities were extracted?",
  "What are the key relationships?",
];

export default function ChatPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamBufferRef = useRef("");
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const createSession = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const data = await apiFetch<{ id: string }>("/chat/sessions", {
          method: "POST",
          token: session.access_token,
          body: { title: "New Chat" },
        });
        setSessionId(data.id);
      } catch (e) {
        console.error("Failed to create chat session:", e);
      } finally {
        setLoading(false);
      }
    };

    createSession();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const flushBuffer = useCallback(() => {
    const buffer = streamBufferRef.current;
    if (!buffer) return;
    streamBufferRef.current = "";
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last && last.role === "assistant") {
        updated[updated.length - 1] = { ...last, content: last.content + buffer };
      }
      return updated;
    });
  }, []);

  const handleSend = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || streaming || !sessionId) return;

    const userMessage = message.trim();
    setMessage("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage },
      { role: "assistant", content: "" },
    ]);
    setStreaming(true);
    streamBufferRef.current = "";
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(
        `${API_BASE}/chat/sessions/${sessionId}/messages`,
        {
          method: "POST",
          signal: controller.signal,
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ message: userMessage }),
        }
      );

      if (!res.ok) throw new Error("Failed to send message");

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";
      let chunkCount = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === "chunk") {
              streamBufferRef.current += data.content;
              chunkCount++;
              if (chunkCount % 10 === 0) flushBuffer();
            } else if (data.type === "citations") {
              flushBuffer();
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  updated[updated.length - 1] = { ...last, citations: data.citations };
                }
                return updated;
              });
            } else if (data.type === "error") {
              flushBuffer();
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  updated[updated.length - 1] = { ...last, content: `Error: ${data.error}` };
                }
                return updated;
              });
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }

      flushBuffer();
    } catch (err) {
      // Abort is expected on unmount/Stop — don't treat as an error
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        console.error("Chat error:", err);
        flushBuffer();
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: "Failed to get response. Make sure the backend is running.",
            };
          }
          return updated;
        });
      }
    } finally {
      if (mountedRef.current) setStreaming(false);
      abortRef.current = null;
    }
  }, [message, streaming, sessionId, flushBuffer, supabase]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    flushBuffer();
  }, [flushBuffer]);

  const setFeedback = useCallback((index: number, value: "up" | "down") => {
    setMessages((prev) => {
      const updated = [...prev];
      const target = updated[index];
      if (target && target.role === "assistant") {
        updated[index] = { ...target, feedback: value };
      }
      return updated;
    });
  }, []);

  const useSuggestion = useCallback((suggestion: string) => {
    setMessage(suggestion);
  }, []);

  return (
    <div className="min-h-screen bg-app-bg flex flex-col">
      <DashboardHeader title="Chat" showBack backHref="/dashboard" />

      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-6 flex flex-col">
        <div className="flex-1 overflow-y-auto mb-4 space-y-4 scrollbar-dark">
          {loading ? (
            <div className="text-center py-20 text-app-muted">
              <p>Connecting to chat...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-lg text-app-muted mb-2">Ask questions about your documents</p>
              <p className="text-sm text-app-muted mb-8">Upload documents in the Document Library to start building your knowledge base</p>
              <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Suggested questions">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => useSuggestion(s)}
                    className="text-sm px-4 py-2 bg-app-card border border-app-border-strong rounded-lg text-app-text hover:bg-app-card-hover hover:border-brand-accent/50 transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-brand-accent/15 text-app-text border border-brand-accent/25"
                      : "bg-app-card border border-app-border-strong text-app-text"
                  }`}
                >
                  {msg.role === "assistant" && msg.content ? (
                    <div className="text-sm [&_pre]:bg-app-surface [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_code]:text-amber [&_p]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_a]:text-brand-accent [&_a]:underline">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  )}
                  {msg.role === "assistant" && !msg.content && streaming && (
                    <div className="flex items-center gap-1 py-1" role="status" aria-label="Assistant is responding">
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-accent animate-bounce [animation-delay:0ms]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-accent animate-bounce [animation-delay:150ms]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-accent animate-bounce [animation-delay:300ms]" />
                    </div>
                  )}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-app-border-strong">
                      <p className="text-xs text-app-muted font-medium mb-1">Sources:</p>
                      <div className="flex flex-wrap gap-1">
                        {msg.citations.map((c, j) => (
                          <span
                            key={j}
                            className="text-xs bg-app-surface text-app-muted px-1.5 py-0.5 rounded font-mono"
                          >
                            [{c.index}] {c.filename} p.{c.page_number}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {msg.role === "assistant" && msg.content && !streaming && (
                    <div className="flex items-center gap-1 mt-2 pt-2 border-t border-app-border-strong">
                      <button
                        onClick={() => setFeedback(i, "up")}
                        aria-label="Helpful"
                        aria-pressed={msg.feedback === "up"}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          msg.feedback === "up"
                            ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                            : "text-app-muted hover:text-app-text hover:bg-app-surface"
                        }`}
                      >
                        👍
                      </button>
                      <button
                        onClick={() => setFeedback(i, "down")}
                        aria-label="Not helpful"
                        aria-pressed={msg.feedback === "down"}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          msg.feedback === "down"
                            ? "bg-red-500/20 text-red-600 dark:text-red-400"
                            : "text-app-muted hover:text-app-text hover:bg-app-surface"
                        }`}
                      >
                        👎
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSend} className="flex gap-2">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!streaming && sessionId && message.trim()) {
                  handleSend(e);
                }
              }
            }}
            placeholder={sessionId ? "Ask a question about your documents... (Enter to send, Shift+Enter for newline)" : "Connecting..."}
            disabled={!sessionId || streaming}
            rows={1}
            className="flex-1 h-10 max-h-40 resize-none py-2 px-4 rounded-lg bg-app-card border border-app-border-strong text-sm text-app-text placeholder:text-slate-600 outline-none focus:border-brand-accent/50 focus:ring-1 focus:ring-brand-accent/20 disabled:opacity-50 transition-all"
          />
          {streaming ? (
            <button
              type="button"
              onClick={stopStreaming}
              className="px-4 h-10 rounded-lg bg-rust/20 text-app-text border border-rust/40 text-sm font-medium hover:bg-rust/30 transition-all"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!sessionId || !message.trim()}
              className="px-4 h-10 rounded-lg bg-brand-accent/15 text-app-text border border-brand-accent/25 text-sm font-medium hover:bg-brand-accent/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              Send
            </button>
          )}
        </form>
      </main>
    </div>
  );
}
