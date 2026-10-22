"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { useAuth } from "@/hooks/useAuth";
import type { SystemStatus } from "@/lib/system-status";

export function StatusIndicator() {
  const { token } = useAuth();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const next = await apiFetch<SystemStatus>("/system/status", { token });
        if (active) { setStatus(next); setError(false); }
      } catch { if (active) setError(true); }
    };
    void refresh();
    const timer = setInterval(() => { void refresh(); }, 30000);
    return () => { active = false; clearInterval(timer); };
  }, [token]);
  return (
    <div className="relative">
      <button onClick={() => setExpanded(!expanded)} aria-expanded={expanded} className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs hover:bg-app-surface">
        <span className={`w-1.5 h-1.5 rounded-full ${error ? "bg-rust" : "bg-amber"}`} />
        {error ? "Status unavailable" : status ? `${status.auth_mode} · ${status.llm.provider}` : "Checking status"}
      </button>
      {expanded && <div className="absolute right-0 top-full mt-1 w-80 rounded-lg border border-app-border bg-app-card shadow-xl p-4 text-xs space-y-3 z-50">
        <div className="flex justify-between"><strong>Service configuration</strong><button onClick={() => setExpanded(false)} aria-label="Close system status">×</button></div>
        {error && <p role="alert">Could not refresh backend status. Any configuration below may be outdated.</p>}
        {status && <>
          <p>Login: {status.auth_mode === "mock" ? "Development mock" : status.auth_mode === "local" ? "Local accounts" : "Supabase"}</p>
          <p>Generation: {status.llm.provider} / {status.llm.model}</p>
          <p>{status.llm.configured ? "Generation configuration present" : "Generation credentials or model missing"}</p>
          <p>Embeddings: {status.embedding.provider} / {status.embedding.model}</p>
          <p>Environment: {status.environment}</p>
          <p className="text-app-muted">Configuration is checked every 30 seconds. Model connectivity and answer quality have not been tested by this indicator.</p>
        </>}
      </div>}
    </div>
  );
}
