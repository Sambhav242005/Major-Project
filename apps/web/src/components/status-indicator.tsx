"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import { m, AnimatePresence } from "motion/react";

interface SystemStatus {
  auth_mode: "local" | "supabase";
  environment: string;
  llm: {
    provider: string;
    ollama_available: boolean;
    ollama_url: string;
    ollama_model: string;
    ollama_models: string[];
    openai_available: boolean;
    openai_model: string;
  };
}

export function StatusIndicator() {
  const supabaseRef = useRef(createClient());
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [expanded, setExpanded] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const { data: { session } } = await supabaseRef.current.auth.getSession();
        setStatus(
          await apiFetch<SystemStatus>("/system/status", {
            token: session?.access_token ?? null,
          })
        );
      } catch {}
    };
    fetchStatus();
  }, []);

  useEffect(() => {
    if (!expanded) return;

    const handleMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [expanded]);

  if (!status) return null;

  const isLocal = status.auth_mode === "local";
  const ollamaUp = status.llm.ollama_available;
  const openaiUp = status.llm.openai_available;
  const llmOk = status.llm.provider === "ollama" ? ollamaUp : openaiUp;
  const activeLlm = status.llm.provider === "ollama"
    ? (ollamaUp ? status.llm.ollama_model : "Ollama offline")
    : (openaiUp ? status.llm.openai_model : "OpenAI key missing");

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-mono hover:bg-app-surface transition-colors"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${isLocal ? "bg-amber" : "bg-emerald-500"}`} />
        <span className="text-app-muted hidden sm:inline">{isLocal ? "Local" : "Supabase"}</span>
        <span className="text-app-muted/50 hidden sm:inline">|</span>
        <span className={`w-1.5 h-1.5 rounded-full ${llmOk ? "bg-emerald-500" : "bg-rust"}`} />
        <span className="text-app-muted hidden sm:inline">
          {status.llm.provider === "ollama" ? "Ollama" : "OpenAI"}
        </span>
      </button>

      <AnimatePresence>
        {expanded && (
          <m.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute right-0 top-full mt-1 w-80 rounded-lg border border-app-border bg-app-card shadow-xl p-4 text-xs space-y-3 z-50"
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold text-app-text">System Status</p>
              <button onClick={() => setExpanded(false)} className="text-app-muted hover:text-app-text">&times;</button>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-app-muted">Auth</span>
                <span className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${isLocal ? "bg-amber" : "bg-emerald-500"}`} />
                  <span className="text-app-text font-medium">{isLocal ? "Local (dev)" : "Supabase"}</span>
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-app-muted">Provider</span>
                <span className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${llmOk ? "bg-emerald-500" : "bg-rust"}`} />
                  <span className="text-app-text font-medium capitalize">{status.llm.provider}</span>
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-app-muted">Model</span>
                <span className="text-app-text font-medium">{activeLlm}</span>
              </div>

              {status.llm.provider === "ollama" && status.llm.ollama_models.length > 0 && (
                <div className="pt-2 border-t border-app-border">
                  <p className="text-app-muted mb-1">Installed models</p>
                  <div className="flex flex-wrap gap-1">
                    {status.llm.ollama_models.map((m) => (
                      <span key={m} className="px-1.5 py-0.5 rounded bg-app-surface text-app-text font-mono text-[10px]">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-2 border-t border-app-border flex items-center justify-between">
                <span className="text-app-muted">Environment</span>
                <span className="text-app-text font-mono">{status.environment}</span>
              </div>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
