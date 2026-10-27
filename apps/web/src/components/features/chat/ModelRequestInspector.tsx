"use client";

import { useState } from "react";
import {
  downloadSnapshot,
  estimatedTokensLabel,
  providerLabel,
  requestMessages,
  snapshotSections,
  statusLabel,
  statusTone,
  type ModelRequestMapping,
} from "@/lib/model-request";

interface InspectorProps {
  mapping: ModelRequestMapping;
}

function messageContentPreview(content: unknown): string {
  if (typeof content === "string") return content;
  if (content === undefined || content === null) return "";
  try {
    return JSON.stringify(content, null, 2);
  } catch {
    return String(content);
  }
}

function KeyValueList({ entries }: { entries: [string, unknown][] }) {
  return (
    <dl className="grid gap-1 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="grid grid-cols-[auto,1fr] gap-2">
          <dt className="font-medium text-app-muted">{key}</dt>
          <dd className="font-mono break-all text-app-text">
            {typeof value === "string" ? value : JSON.stringify(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Read-only "Model request" inspector for one assistant turn.
 *
 * Shows the captured sanitized payload — never a draft preview — with
 * expandable sections, copy and download of the exact JSON the backend
 * captured at the transport boundary.
 */
export function ModelRequestInspector({ mapping }: InspectorProps) {
  const { snapshot } = mapping;
  const [openSection, setOpenSection] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const sections = snapshotSections(snapshot);
  const messages = requestMessages(snapshot);

  const copyPayload = async () => {
    if (!snapshot) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(snapshot, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions); download remains available.
    }
  };

  return (
    <div className="mt-2 rounded-lg border border-app-border bg-app-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-app-muted">Model request</span>
        <span
          className={`rounded border px-1.5 py-0.5 text-xs font-medium ${statusTone(snapshot)}`}
          aria-label="Request status"
        >
          {statusLabel(snapshot)}
        </span>
        <span className="text-xs text-app-muted">{providerLabel(snapshot)}</span>
        <span className="text-xs text-app-muted">{estimatedTokensLabel(snapshot)}</span>
      </div>

      {snapshot ? (
        <>
          <p className="mt-1 text-xs text-app-muted">
            Captured {snapshot.captured_at ? `at ${snapshot.captured_at}` : "during the request"} — what
            this application actually supplied to the provider. Read-only; secrets and hidden reasoning
            are excluded.
          </p>
          {snapshot.status === "failed" && snapshot.failure_reason && (
            <p className="mt-1 text-xs text-rust" role="alert">
              Failure: {snapshot.failure_reason}
            </p>
          )}

          <div className="mt-2 space-y-1">
            {sections.map((section) => {
              const open = openSection === section.id;
              return (
                <div key={section.id} className="rounded border border-app-border">
                  <button
                    type="button"
                    aria-expanded={open}
                    onClick={() => setOpenSection(open ? null : section.id)}
                    className="flex w-full items-center justify-between px-2 py-1.5 text-left text-xs hover:bg-app-card"
                  >
                    <span>
                      <span className="font-medium text-app-text">{section.title}</span>{" "}
                      <span className="text-app-muted">— {section.summary}</span>
                    </span>
                    <span aria-hidden>{open ? "▾" : "▸"}</span>
                  </button>
                  {open && (
                    <div className="border-t border-app-border px-2 py-2">
                      {section.id === "messages" && (
                        <div className="space-y-2">
                          {messages.map((message, index) => (
                            <div key={index} className="rounded bg-app-card p-2">
                              <p className="mb-1 font-mono text-xs text-amber">{message.role ?? "unknown"}</p>
                              <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-app-text">
                                {messageContentPreview(message.content)}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                      {section.id === "retrieval" && snapshot.assembly?.retrieval && (
                        <div className="space-y-2">
                          {snapshot.assembly.retrieval.sources?.map((source) => (
                            <div key={source.index} className="rounded bg-app-card p-2">
                              <p className="text-xs text-app-muted">
                                [Source {source.index}] {source.filename} · p.{source.page_number || "N/A"}
                                {source.truncated && (
                                  <span className="ml-2 rounded border border-amber/40 px-1 text-amber">
                                    truncated to {snapshot.assembly?.retrieval?.source_text_truncated_to_chars} of{" "}
                                    {source.original_characters} chars
                                  </span>
                                )}
                              </p>
                              <p className="font-mono text-[10px] text-app-muted">
                                chunk {source.chunk_id} · document {source.document_id}
                              </p>
                              <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-app-text">
                                {source.text}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                      {section.id === "graph" && snapshot.assembly?.graph_context && (
                        <KeyValueList
                          entries={Object.entries(snapshot.assembly.graph_context)}
                        />
                      )}
                      {section.id === "history" && (
                        <div className="space-y-1 text-xs">
                          {snapshot.assembly?.history?.entries?.map((entry, index) => (
                            <div key={index} className="rounded bg-app-card p-2">
                              <p className="font-mono text-xs text-amber">
                                {entry.role}
                                {entry.truncated && (
                                  <span className="ml-2 text-app-muted">
                                    clipped to {snapshot.assembly?.history?.assistant_clipped_to_chars ?? "??"} chars
                                  </span>
                                )}
                              </p>
                              <pre className="whitespace-pre-wrap break-words text-app-text">{entry.content}</pre>
                            </div>
                          ))}
                        </div>
                      )}
                      {section.id === "settings" && (
                        <KeyValueList entries={Object.entries(snapshot.generation_settings ?? {})} />
                      )}
                      {section.id === "transport" && (
                        <div className="space-y-2 text-xs">
                          <KeyValueList
                            entries={Object.entries({
                              method: snapshot.request?.method ?? "POST",
                              url: snapshot.request?.url ?? "",
                              ...(snapshot.request?.headers ?? {}),
                            })}
                          />
                        </div>
                      )}
                      {section.id === "privacy" && (
                        <div className="space-y-2">
                          <KeyValueList entries={Object.entries(snapshot.sanitization ?? {})} />
                          <KeyValueList entries={Object.entries(snapshot.retention ?? {})} />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => { void copyPayload(); }}
              className="rounded border border-app-border px-2 py-1 text-xs text-app-text hover:bg-app-card"
            >
              {copied ? "Copied" : "Copy request JSON"}
            </button>
            <button
              type="button"
              onClick={() => snapshot && downloadSnapshot(snapshot)}
              className="rounded border border-app-border px-2 py-1 text-xs text-app-text hover:bg-app-card"
            >
              Download JSON
            </button>
          </div>
        </>
      ) : (
        <p className="mt-1 text-xs text-app-muted">
          The captured request record for this turn is unavailable — it may have expired after its
          30-minute in-process retention window or the backend was restarted before you opened this
          view. The request itself is not stored in the database.
        </p>
      )}
    </div>
  );
}
