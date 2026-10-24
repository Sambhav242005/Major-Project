"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, withProject } from "@/lib/api/client";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { useProjectStore } from "@/stores/project";
import { ChatBubble, ChatSuggestions, ChatInput, ChatHeader } from "@/components/features/chat";
import type { ChatMessage } from "@/components/features/chat";
import { readChatStream } from "@/lib/chat-stream";
import type { SystemStatus } from "@/lib/system-status";

export default function ChatPage() {
  const [supabase] = useState(() => createClient());

  const [message, setMessage] = useState("");
  const [provider, setProvider] = useState("configured");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [defaultModel, setDefaultModel] = useState("Server default");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamBufferRef = useRef("");
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const { projects, activeProjectId } = useProjectStore();
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const status = await apiFetch<SystemStatus>("/system/status", { token: session.access_token });
        if (active) setDefaultModel(`${status.llm.provider} / ${status.llm.model}`);
      } catch { /* Sending still works with the server default. */ }
    })();
    return () => { active = false; };
  }, [supabase]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const createSession = useCallback(async () => {
    abortRef.current?.abort();
    setLoading(true);
    setMessages([]);
    setSessionId(null);
    setSessionError(null);

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
      setSessionError(e instanceof Error ? e.message : "Failed to create chat session");
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
    if (provider !== "configured" && !model.trim()) {
      setGenerationError("Enter the model ID supplied by your provider.");
      return;
    }
    if (!["configured", "chatgpt"].includes(provider) && !apiKey.trim()) {
      setGenerationError("Enter an API key for this provider.");
      return;
    }
    setGenerationError(null);
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
      if (!session) throw new Error("Your session expired. Sign in again.");
      const res = await fetch(withProject(`/chat/sessions/${sessionId}/messages`, activeProjectId), {
        method: "POST",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage,
          generation: {
            provider,
            ...(model.trim() ? { model: model.trim() } : {}),
            ...(!["configured", "chatgpt"].includes(provider) ? { api_key: apiKey.trim() } : {}),
          },
        }),
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(typeof error.detail === "string" ? error.detail : "Could not send message. Check your model and provider settings.");
      }
      if (!res.body) throw new Error("No response stream received");
      let chunkCount = 0;
      for await (const data of readChatStream(res.body)) {
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
        }
      }
      flushBuffer();
    } catch (err) {
      if (mountedRef.current) {
        console.error("Chat error:", err);
        streamBufferRef.current = "";
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: controller.signal.aborted ? "Response stopped before completion. Send the question again to retry." : err instanceof Error ? err.message : "Failed to get a complete response. Please try again.",
              citations: [],
            };
          }
          return updated;
        });
      }
    } finally {
      if (mountedRef.current) setStreaming(false);
      abortRef.current = null;
    }
  }, [message, streaming, sessionId, flushBuffer, supabase, activeProjectId, provider, model, apiKey]);

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
        {sessionError && <p role="alert" className="text-sm text-red-400 mb-4">{sessionError} <button onClick={() => { void createSession(); }} className="underline">Retry connection</button></p>}
        <ChatHeader
          projectName={activeProject?.name ?? null}
          onNewSession={sessionId ? () => { void createSession(); } : undefined}
          isStreaming={streaming}
        />
        <fieldset disabled={streaming} className="mb-5 rounded-xl border border-app-border bg-app-card p-4 space-y-3 disabled:opacity-60">
          <legend className="px-1 text-sm font-medium">Chat model</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-app-muted space-y-1">
              <span>Provider</span>
              <select value={provider} onChange={(event) => {
                setProvider(event.target.value); setModel(""); setApiKey(""); setGenerationError(null);
              }} className="block w-full rounded-md border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text">
                <option value="configured">Server configured · {defaultModel}</option>
                <option value="openai">OpenAI API</option>
                <option value="groq">Groq</option>
                <option value="openrouter">OpenRouter</option>
                <option value="gemini">Google Gemini</option>
                <option value="chatgpt">ChatGPT (server connection)</option>
              </select>
            </label>
            <label className="text-xs text-app-muted space-y-1">
              <span>Model ID {provider === "configured" ? "(optional override)" : "(required)"}</span>
              <input value={model} onChange={(event) => { setModel(event.target.value); setGenerationError(null); }} maxLength={200}
                placeholder={provider === "configured" ? defaultModel : "Enter your provider’s model ID"}
                className="block w-full rounded-md border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text" />
            </label>
          </div>
          {!["configured", "chatgpt"].includes(provider) && <label className="block text-xs text-app-muted space-y-1">
            <span>Provider API key (required)</span>
            <input type="password" autoComplete="off" value={apiKey} onChange={(event) => { setApiKey(event.target.value); setGenerationError(null); }}
              className="block w-full rounded-md border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text" />
          </label>}
          <p className="text-xs text-app-muted">Applies to your next chat message. Selections reset when you leave this page. API keys are sent to the backend and kept only in page memory. ChatGPT requires an existing server login. Documents and embeddings keep their server settings.</p>
          {generationError && <p role="alert" className="text-sm text-rust">{generationError}</p>}
        </fieldset>
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
