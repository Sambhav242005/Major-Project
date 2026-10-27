"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, withProject } from "@/lib/api/client";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { useProjectStore } from "@/stores/project";
import { ChatBubble, ChatSuggestions, ChatInput, ChatHeader } from "@/components/features/chat";
import type { ChatMessage } from "@/components/features/chat";
import { readChatStream } from "@/lib/chat-stream";
import {
  buildGenerationPayload,
  defaultChatProviderAvailability,
  useChatModelSelection,
  validateChatSelection,
  type ChatProviderAvailability,
} from "@/lib/chat-selection";
import type { SystemStatus } from "@/lib/system-status";

export default function ChatPage() {
  const [supabase] = useState(() => createClient());

  const [message, setMessage] = useState("");
  const selection_ = useChatModelSelection();
  const [defaultModel, setDefaultModel] = useState("");
  const [providerAvailability, setProviderAvailability] = useState<ChatProviderAvailability>(
    defaultChatProviderAvailability,
  );
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
        if (active) {
          setDefaultModel(`${status.llm.provider} / ${status.llm.model}`);
          setProviderAvailability({
            serverLlmConfigured: status.llm.configured,
            serverChatGptConnected: Boolean(status.capabilities.chatgpt),
          });
        }
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

  const patchLastAssistant = useCallback((patch: Partial<ChatMessage>) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last && last.role === "assistant") {
        updated[updated.length - 1] = { ...last, ...patch };
      }
      return updated;
    });
  }, []);

  const handleSend = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!message.trim() || streaming || !sessionId) return;
    const validationError = validateChatSelection(selection_.selection, providerAvailability);
    if (validationError) {
      selection_.setGenerationError(validationError);
      return;
    }
    selection_.setGenerationError(null);
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
        // The payload is frozen from the selection at send time, so switching
        // the header selector mid-stream cannot affect the running request.
        body: JSON.stringify({
          message: userMessage,
          generation: buildGenerationPayload(selection_.selection),
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
          patchLastAssistant({ citations: data.citations });
        } else if (data.type === "generation") {
          // Label this answer with the model the backend actually used, so
          // later header changes cannot mislabel it.
          patchLastAssistant({ generation: { provider: data.provider, model: data.model } });
        }
      }
      flushBuffer();
    } catch (err) {
      if (mountedRef.current) {
        console.error("Chat error:", err);
        streamBufferRef.current = "";
        patchLastAssistant({
          content: controller.signal.aborted ? "Response stopped before completion. Send the question again to retry." : err instanceof Error ? err.message : "Failed to get a complete response. Please try again.",
          citations: [],
        });
      }
    } finally {
      if (mountedRef.current) setStreaming(false);
      abortRef.current = null;
    }
  }, [message, streaming, sessionId, flushBuffer, patchLastAssistant, supabase, activeProjectId, selection_, providerAvailability]);

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
          selection={selection_.selection}
          defaultModel={defaultModel}
          availability={providerAvailability}
          error={selection_.error}
          onProviderChange={selection_.setProvider}
          onModelChange={selection_.setModel}
          onApiKeyChange={selection_.setApiKey}
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
