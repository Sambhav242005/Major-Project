"use client";

const SUGGESTIONS = [
  "Summarize my documents",
  "What entities were extracted?",
  "What are the key relationships?",
];

interface ChatSuggestionsProps {
  onSelect: (suggestion: string) => void;
}

export function ChatSuggestions({ onSelect }: ChatSuggestionsProps) {
  return (
    <div className="text-center py-20">
      <p className="text-lg text-app-muted mb-2">Ask questions about your documents</p>
      <p className="text-sm text-app-muted mb-8">
        Upload documents in the Document Library to start building your knowledge base
      </p>
      <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Suggested questions">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSelect(s)}
            className="text-sm px-4 py-2 bg-app-card border border-app-border-strong rounded-lg text-app-text hover:bg-app-card-hover hover:border-brand-accent/50 transition-all"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
