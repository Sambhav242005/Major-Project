"use client";

interface ChatHeaderProps {
  projectName: string | null;
  onNewSession?: () => void;
  isStreaming?: boolean;
}

export function ChatHeader({ projectName, onNewSession, isStreaming }: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3 text-sm">
        <span className="text-app-muted">Project:</span>
        <span className="font-medium text-app-text">{projectName ?? "—"}</span>
      </div>
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
  );
}
