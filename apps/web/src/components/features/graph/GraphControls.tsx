"use client";

interface GraphControlsProps {
  depth: number;
  onDepthChange: (depth: number) => void;
  onRefresh: () => void;
  onFitView: () => void;
  loading: boolean;
}

export function GraphControls({ depth, onDepthChange, onRefresh, onFitView, loading }: GraphControlsProps) {
  return (
    <>
      <div>
        <label className="text-xs text-app-muted uppercase tracking-wider mb-1.5 block">
          Depth: {depth}
        </label>
        <input
          type="range"
          min={1}
          max={3}
          value={depth}
          onChange={(e) => onDepthChange(Number(e.target.value))}
          className="w-full accent-brand-accent"
        />
        <div className="flex justify-between text-xs text-app-muted mt-1">
          <span>1</span>
          <span>2</span>
          <span>3</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={onRefresh}
          disabled={loading}
          className="h-9 px-3 rounded-lg bg-app-surface text-app-text border border-app-border-strong text-sm font-medium hover:bg-app-card-hover disabled:opacity-40 transition-all"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
        <button
          onClick={onFitView}
          className="h-9 px-3 rounded-lg bg-app-surface text-app-text border border-app-border-strong text-sm font-medium hover:bg-app-card-hover transition-all"
        >
          Fit view
        </button>
      </div>
    </>
  );
}
