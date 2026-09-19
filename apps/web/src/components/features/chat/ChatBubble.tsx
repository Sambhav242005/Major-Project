"use client";

import ReactMarkdown from "react-markdown";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: { index: number; filename: string; page_number: number }[];
  feedback?: "up" | "down";
}

interface ChatBubbleProps {
  message: ChatMessage;
  onFeedback?: (value: "up" | "down") => void;
  isStreaming?: boolean;
}

export function ChatBubble({ message, onFeedback, isStreaming }: ChatBubbleProps) {
  const { role, content, citations, feedback } = message;
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
          isUser
            ? "bg-brand-accent/15 text-app-text border border-brand-accent/25"
            : "bg-app-card border border-app-border-strong text-app-text"
        }`}
      >
        {!isUser && content ? (
          <div className="text-sm [&_pre]:bg-app-surface [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_code]:text-amber [&_p]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_a]:text-brand-accent [&_a]:underline">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        ) : (
          <div className="whitespace-pre-wrap">{content}</div>
        )}

        {!isUser && !content && isStreaming && (
          <div className="flex items-center gap-1 py-1" role="status" aria-label="Assistant is responding">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-accent animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-brand-accent animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-brand-accent animate-bounce [animation-delay:300ms]" />
          </div>
        )}

        {citations && citations.length > 0 && (
          <div className="mt-2 pt-2 border-t border-app-border-strong">
            <p className="text-xs text-app-muted font-medium mb-1">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {citations.map((c, j) => (
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

        {!isUser && content && !isStreaming && onFeedback && (
          <div className="flex items-center gap-1 mt-2 pt-2 border-t border-app-border-strong">
            <button
              onClick={() => onFeedback("up")}
              aria-label="Helpful"
              aria-pressed={feedback === "up"}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                feedback === "up"
                  ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                  : "text-app-muted hover:text-app-text hover:bg-app-surface"
              }`}
            >
              👍
            </button>
            <button
              onClick={() => onFeedback("down")}
              aria-label="Not helpful"
              aria-pressed={feedback === "down"}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                feedback === "down"
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
  );
}
