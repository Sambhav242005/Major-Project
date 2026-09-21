"use client";

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "#f59e0b",
  ORG: "#22c55e",
  GPE: "#64748b",
  EVENT: "#ef4444",
  CONCEPT: "#38bdf8",
};

export function GraphLegend() {
  return (
    <div className="mt-auto">
      <p className="text-[10px] text-app-muted uppercase tracking-wider mb-2">Legend</p>
      <div className="space-y-1.5">
        {Object.entries(ENTITY_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-2 text-xs">
            <div className="w-2.5 h-2.5 rounded" style={{ backgroundColor: color }} />
            <span className="text-app-muted">{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
