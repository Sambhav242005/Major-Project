"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api/client";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { useProjectStore } from "@/stores/project";
import { ChatBubble, ChatSuggestions, ChatInput, ChatHeader } from "@/components/features/chat";
import type { ChatMessage } from "@/components/features/chat";

export default function ChatPage() {
  const [supabase] = useState(() => createClient());

  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamBufferRef = useRef("");
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const { projects, activeProjectId } = useProjectStore();
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const createSession = useCallback(async () => {
    setLoading(true);
    setMessages([]);
    setSessionId(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      if (!activeProjectId) return;

      const data = await apiFetch<{ id: string }>("/chat/sessions", {
        method: "POST",
        token: session.access_token,
        projectId: activeProjectId,
        body: { title: "New Chat" },
      });

      if (mountedRef.current) {
        setSessionId(data.id);
      }
    } catch (e) {
      console.error("Failed to create chat session:", e);
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [activeProjectId, supabase.auth]);

  useEffect(() => {
    if (!activeProjectId) return;
    void createSession();
  }, [activeProjectId, createSession]);

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

  const handleSend = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();
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
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: userMessage }),
      });
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
          } catch { /* Skip malformed JSON */ }
        }
      }
      flushBuffer();
    } catch (err) {
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

  return (
    <div className="min-h-screen bg-app-bg flex flex-col">
      <DashboardHeader title="Chat" showBack backHref="/dashboard" />
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-6 flex flex-col">
        <ChatHeader
          projectName={activeProject?.name ?? null}
          onNewSession={sessionId ? () => { void createSession(); } : undefined}
          isStreaming={streaming}
        />
        <div className="flex-1 overflow-y-auto mb-4 space-y-4 scrollbar-dark">
          {loading ? (
            <div className="text-center py-20 text-app-muted">
              <p>Connecting to chat...</p>
            </div>
          ) : messages.length === 0 ? (
            <ChatSuggestions onSelect={setMessage} />
          ) : (
            messages.map((msg, i) => (
              <ChatBubble
                key={i}
                message={msg}
                isStreaming={streaming}
                onFeedback={
                  msg.role === "assistant" && msg.content && !streaming
                    ? (v) => setFeedback(i, v)
                    : undefined
                }
              />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
        <ChatInput
          value={message}
          onChange={setMessage}
          onSend={() => {
            void handleSend();
          }}
          onStop={stopStreaming}
          isStreaming={streaming}
          disabled={!sessionId}
        />
      </main>
    </div>
  );
}
