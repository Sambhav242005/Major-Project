"use client";

import type { EntityChunk, EntityDetail } from "@/lib/types";

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "#f59e0b",
  ORG: "#22c55e",
  GPE: "#64748b",
  EVENT: "#ef4444",
  CONCEPT: "#38bdf8",
};

interface EntityDetailPanelProps {
  entity: EntityDetail | null;
  chunks: EntityChunk[];
}

export function EntityDetailPanel({
  entity,
  chunks,
}: EntityDetailPanelProps) {
  if (!entity) return null;

  return (
    <>
      <div className="glow-card p-4 mt-2">
        <h3 className="text-sm font-medium text-app-text mb-2">
          {entity.name}
        </h3>

        <span
          className="text-[10px] px-1.5 py-0.5 rounded inline-block mb-2"
          style={{
            background: `${ENTITY_COLORS[entity.type] ?? "#64748b"}20`,
            color: ENTITY_COLORS[entity.type] ?? "#64748b",
            border: `1px solid ${ENTITY_COLORS[entity.type] ?? "#64748b"}40`,
          }}
        >
          {entity.type}
        </span>

        {entity.description && (
          <p className="text-xs text-app-muted mb-2">{entity.description}</p>
        )}

        <div className="text-[10px] text-app-muted">
          Mentions: {entity.mentions_count ?? 0}
        </div>

        {entity.relationships && entity.relationships.length > 0 && (
          <div className="mt-3">
            <p className="text-[10px] text-app-muted uppercase tracking-wider mb-1">
              Relationships
            </p>

            <div className="space-y-1">
              {entity.relationships.map((rel) => (
                <div key={rel.id} className="text-[11px] text-app-muted">
                  <span className="text-app-text">
                    {rel.other_entity_name}
                  </span>{" "}
                  <span className="text-app-muted">
                    ({rel.relation_type})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {chunks.length > 0 && (
        <div className="mt-2">
          <p className="text-[10px] text-app-muted uppercase tracking-wider mb-2">
            Source sections ({chunks.length})
          </p>

          <div className="space-y-2">
            {chunks.map((chunk, idx) => (
              <div
                key={chunk.chunk_id ?? idx}
                className="rounded-lg border border-app-border bg-app-surface p-2.5"
              >
                <div className="flex items-center justify-between mb-1 gap-2">
                  <span className="text-[10px] font-mono text-app-muted truncate">
                    {chunk.filename}
                  </span>

                  <span className="text-[10px] font-mono text-app-muted shrink-0">
                    p.{chunk.page_number ?? "?"}
                  </span>
                </div>

                <p className="text-[11px] leading-relaxed text-app-text line-clamp-4">
                  {chunk.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
