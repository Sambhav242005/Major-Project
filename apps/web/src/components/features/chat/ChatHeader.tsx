"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDownIcon } from "lucide-react";
import {
  MAX_MODEL_LENGTH,
  chatProviderMeta,
  chatProviderUnavailableReason,
  chatProviders,
  chatSelectionLabel,
  type ChatModelSelection,
  type ChatProviderAvailability,
  type ChatProviderId,
} from "@/lib/chat-selection";

interface ChatHeaderProps {
  projectName: string | null;
  onNewSession?: () => void;
  isStreaming?: boolean;
  /** Shared with the send handler — see useChatModelSelection. */
  selection: ChatModelSelection;
  defaultModel: string;
  availability: ChatProviderAvailability;
  error: string | null;
  onProviderChange: (provider: ChatProviderId) => void;
  onModelChange: (model: string) => void;
  onApiKeyChange: (apiKey: string) => void;
}

export function ChatHeader({
  projectName,
  onNewSession,
  isStreaming,
  selection,
  defaultModel,
  availability,
  error,
  onProviderChange,
  onModelChange,
  onApiKeyChange,
}: ChatHeaderProps) {
  const [open, setOpen] = useState(false);
  const chipRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const unavailable = chatProviderUnavailableReason(selection.provider, availability);

  // A send-time validation error is displayed inside the panel; open it so the
  // reason is never invisible behind a closed chip.
  useEffect(() => {
    if (error) setOpen(true);
  }, [error]);

  // Mouse and keyboard dismissal: Escape returns focus to the chip.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        chipRef.current?.focus();
      }
    };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!panelRef.current?.contains(target) && !chipRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  const meta = chatProviderMeta(selection.provider);

  return (
    <div className="relative flex items-center justify-between mb-4 gap-2">
      <div className="flex items-center gap-3 text-sm min-w-0">
        <span className="text-app-muted shrink-0">Project:</span>
        <span className="font-medium text-app-text truncate">{projectName ?? "—"}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          ref={chipRef}
          onClick={() => setOpen((value) => !value)}
          aria-haspopup="dialog"
          aria-expanded={open}
          title="Change the model used by your next message"
          className="flex items-center gap-1 max-w-[16rem] text-xs px-3 py-1.5 rounded-lg bg-app-surface border border-app-border-strong text-app-text hover:border-brand-accent transition-colors"
        >
          <span className="truncate font-mono">{chatSelectionLabel(selection, defaultModel)}</span>
          <ChevronDownIcon size={12} className={`shrink-0 text-app-muted transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {onNewSession && (
          <button
            onClick={onNewSession}
            disabled={isStreaming}
            className="text-xs px-3 py-1.5 rounded-lg bg-app-surface border border-app-border-strong text-app-muted hover:text-app-text transition-colors disabled:opacity-40"
          >
            New session
          </button>
        )}
      </div>

      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="Chat model selector"
          className="absolute right-0 top-full mt-2 z-50 w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-app-border bg-app-card p-4 space-y-3 shadow-lg"
        >
          <div>
            <p className="text-sm font-medium text-app-text">Chat model</p>
            <p className="text-xs text-app-muted">Applies to your next chat message. An answer already streaming keeps its model.</p>
          </div>

          <label className="block text-xs text-app-muted space-y-1">
            <span>Provider</span>
            <select
              autoFocus
              value={selection.provider}
              onChange={(event) => onProviderChange(event.target.value as ChatProviderId)}
              className="block w-full rounded-md border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text"
            >
              {chatProviders().map((provider) => {
                const reason = chatProviderUnavailableReason(provider.id, availability);
                return (
                  <option key={provider.id} value={provider.id}>
                    {provider.label}{reason ? " — unavailable" : ""}
                  </option>
                );
              })}
            </select>
          </label>

          <label className="block text-xs text-app-muted space-y-1">
            <span>Model ID {selection.provider === "configured" ? "(optional override)" : "(required)"}</span>
            <input
              value={selection.model}
              onChange={(event) => onModelChange(event.target.value)}
              maxLength={MAX_MODEL_LENGTH}
              placeholder={selection.provider === "configured" ? defaultModel : "Enter your provider’s model ID"}
              className="block w-full rounded-md border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text"
            />
          </label>

          {meta.requiresApiKey && (
            <label className="block text-xs text-app-muted space-y-1">
              <span>Provider API key (required)</span>
              <input
                type="password"
                autoComplete="off"
                value={selection.apiKey}
                onChange={(event) => onApiKeyChange(event.target.value)}
                className="block w-full rounded-md border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text"
              />
            </label>
          )}

          {unavailable && <p role="alert" className="text-xs text-rust">{unavailable}</p>}
          {error && <p role="alert" className="text-xs text-rust">{error}</p>}

          <p className="text-xs text-app-muted">
            Server default: <span className="font-mono">{defaultModel || "not reported"}</span>. API keys are sent to the backend
            and kept only in page memory. Selections reset when you leave this page. ChatGPT requires an existing server login.
          </p>
        </div>
      )}
    </div>
  );
}
