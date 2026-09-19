"use client";

import { KeyboardEvent } from "react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming,
  disabled,
  placeholder = "Ask a question about your documents... (Enter to send, Shift+Enter for newline)",
}: ChatInputProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && !disabled && value.trim()) {
        onSend();
      }
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!isStreaming && !disabled && value.trim()) onSend();
      }}
      className="flex gap-2"
    >
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Connecting..." : placeholder}
        disabled={disabled}
        rows={1}
        className="flex-1 h-10 max-h-40 resize-none py-2 px-4 rounded-lg bg-app-card border border-app-border-strong text-sm text-app-text placeholder:text-slate-600 outline-none focus:border-brand-accent/50 focus:ring-1 focus:ring-brand-accent/20 disabled:opacity-50 transition-all"
      />
      {isStreaming ? (
        <button
          type="button"
          onClick={onStop}
          className="px-4 h-10 rounded-lg bg-rust/20 text-app-text border border-rust/40 text-sm font-medium hover:bg-rust/30 transition-all"
        >
          Stop
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="px-4 h-10 rounded-lg bg-brand-accent/15 text-app-text border border-brand-accent/25 text-sm font-medium hover:bg-brand-accent/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          Send
        </button>
      )}
    </form>
  );
}
