"use client";

interface GraphTypeFilterProps {
  entityTypes: string[];
  activeFilters: string[];
  onToggle: (type: string) => void;
}

export function GraphTypeFilter({ entityTypes, activeFilters, onToggle }: GraphTypeFilterProps) {
  if (entityTypes.length === 0) return null;

  return (
    <div>
      <label className="text-xs text-app-muted uppercase tracking-wider mb-1.5 block">
        Filter by type {activeFilters.length > 0 && `(${activeFilters.length})`}
      </label>
      <div className="flex flex-wrap gap-1.5">
        {entityTypes.map((type) => (
          <button
            key={type}
            onClick={() => onToggle(type)}
            aria-pressed={activeFilters.includes(type)}
            className={`text-[11px] px-2 py-1 rounded-full border transition-colors ${
              activeFilters.includes(type)
                ? "bg-brand-accent/20 border-brand-accent/40 text-app-text"
                : "bg-app-surface border-app-border-strong text-app-muted hover:text-app-text"
            }`}
          >
            {type}
          </button>
        ))}
      </div>
    </div>
  );
}
