"use client";

import { useGraphStore } from "@/stores/graph";

interface GraphSearchProps {
  onSearch: () => void;
}

export function GraphSearch({ onSearch }: GraphSearchProps) {
  const { searchQuery, setSearchQuery } = useGraphStore();

  return (
    <div>
      <label className="text-xs text-app-muted uppercase tracking-wider mb-1.5 block">
        Search Entity
      </label>
      <div className="flex gap-2">
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Entity name..."
          onKeyDown={(e) => e.key === "Enter" && onSearch()}
          className="flex-1 h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text placeholder:text-app-muted outline-none focus:border-brand-accent/50 transition-all"
        />
        <button
          onClick={onSearch}
          className="h-9 px-3 rounded-lg bg-brand-accent/15 text-app-text border border-brand-accent/25 text-sm font-medium hover:bg-brand-accent/25 transition-all"
        >
          Go
        </button>
      </div>
    </div>
  );
}
