/**
 * Chat sessions: list, create, send messages with SSE streaming.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, withProject, API_BASE } from "@/lib/api/client";
import { ChatSession, ChatMessage } from "@/lib/validators";

interface UseChatOptions {
  token: string | null;
  projectId: string | null;
}

export function useChat({ token, projectId }: UseChatOptions) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchSessions = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const data = await apiFetch<ChatSession[]>("/chat/sessions", { token, projectId });
      setSessions(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const selectSession = useCallback(
    async (sessionId: string) => {
      if (!token) return;
      setActiveSessionId(sessionId);
      try {
        const data = await apiFetch<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`, { token });
        setMessages(Array.isArray(data) ? data : []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load messages");
      }
    },
    [token]
  );

  const createSession = useCallback(async () => {
    if (!token || !projectId) return null;
    try {
      const session = await apiFetch<ChatSession>("/chat/sessions", {
        method: "POST",
        token,
        projectId,
        body: { title: "New Chat" },
      });
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
      return session;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create session");
      return null;
    }
  }, [token, projectId]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!token || !activeSessionId) return;

      // Add user message optimistically
      const userMsg = {
        id: crypto.randomUUID(),
        role: "user" as const,
        content,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setSending(true);
      setError(null);

      // SSE stream the assistant response
      abortRef.current = new AbortController();
      try {
        const url = withProject(`/chat/sessions/${activeSessionId}/messages`, projectId);
        const res = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ content }),
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "Failed to send message");
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response stream");

        const decoder = new TextDecoder();
        let assistantContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          assistantContent += chunk;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [...prev.slice(0, -1), { ...last, content: assistantContent }];
            }
            return [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: assistantContent,
                created_at: new Date().toISOString(),
              },
            ];
          });
        }
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setError(e instanceof Error ? e.message : "Failed to send message");
        }
      } finally {
        setSending(false);
        abortRef.current = null;
      }
    },
    [token, activeSessionId, projectId]
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    setSending(false);
  }, []);

  return {
    sessions,
    activeSessionId,
    messages,
    loading,
    sending,
    error,
    selectSession,
    createSession,
    sendMessage,
    stopGeneration,
    refresh: fetchSessions,
  };
}
