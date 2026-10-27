/**
 * "Model request" snapshot helpers (TODO 2.24 — Phase 1).
 *
 * A snapshot is the sanitized record of what the application actually sent to
 * the chat provider for one assistant turn, captured at the final transport
 * boundary and served read-only by `GET /chat/model-requests/{request_id}`.
 * Nothing here rewrites what was sent: the view either renders the captured
 * payload or honestly reports that no captured record is available.
 */

export type ModelRequestAttachment = never; // attachments are a documented follow-up

export interface ModelRequestSnapshot {
  schema?: string;
  request_id: string;
  /** "sent" | "failed" | "cancelled" — echoes what happened to the request. */
  status?: string | null;
  failure_reason?: string | null;
  captured_at?: string | null;
  project_id?: string;
  session_id?: string;
  provider?: {
    provider?: string;
    model?: string;
    endpoint?: string;
    request_shape?: string;
  };
  generation_settings?: Record<string, unknown>;
  request?: {
    method?: string;
    url?: string;
    headers?: Record<string, string>;
    body?: {
      messages?: ModelRequestMessage[];
      input?: ModelRequestMessage[];
      [key: string]: unknown;
    };
  };
  token_counts?: {
    estimate?: boolean;
    method?: string;
    total?: number;
    by_message?: { role?: string; estimated_tokens?: number }[];
    request_body_characters?: number;
  };
  assembly?: {
    flow?: string;
    session_id?: string;
    user_message?: { role?: string; content?: string };
    history?: {
      window_limit?: number;
      rows_returned_by_window?: number;
      included_entries?: number;
      assistant_clipped_to_chars?: number;
      may_exclude_older_messages?: boolean;
      entries?: { role: string; content: string; truncated: boolean }[];
    };
    retrieval?: {
      top_k?: number;
      query?: string;
      source_count?: number;
      source_text_truncated_to_chars?: number;
      sources?: {
        index: number;
        chunk_id: string;
        document_id: string;
        filename: string;
        page_number: number;
        text: string;
        truncated: boolean;
        original_characters: number;
      }[];
      truncation_decisions?: string;
    };
    graph_context?: {
      entities?: { id?: string; name?: string; type?: string; description?: string }[];
      entities_shown_in_prompt?: number;
      entities_omitted?: number;
      expanded?: { id?: string; name?: string; type?: string; description?: string }[];
      expanded_shown_in_prompt?: number;
      expanded_omitted?: number;
    };
    attachments?: unknown[];
    tools?: { present?: boolean };
  };
  sanitization?: Record<string, unknown>;
  retention?: Record<string, unknown>;
  attachments?: unknown[];
  tools?: { present?: boolean };
}

/**
 * A single prompt message as rendered by the inspector. Multimodal (array)
 * content parts are shown through their full JSON, with binary payloads
 * already withheld by the server.
 */
export interface ModelRequestMessage {
  role?: string;
  content?: unknown;
}

export type ModelRequestSnapshotState = "fetched" | "missing";

export interface ModelRequestMapping {
  requestId: string;
  state: ModelRequestSnapshotState;
  snapshot: ModelRequestSnapshot | null;
}

export interface ModelRequestSection {
  id: "messages" | "retrieval" | "graph" | "history" | "settings" | "transport" | "privacy";
  title: string;
  summary: string;
}

/** Messages actually present in the captured request body, in send order. */
export function requestMessages(snapshot: ModelRequestSnapshot | null): ModelRequestMessage[] {
  const body = snapshot?.request?.body;
  if (!body) return [];
  return body.messages ?? body.input ?? [];
}

function windowNote(snapshot: ModelRequestSnapshot | null): string {
  const history = snapshot?.assembly?.history;
  if (!history) return "";
  const included = history.included_entries ?? 0;
  const older = history.may_exclude_older_messages
    ? "older messages beyond the window may be excluded"
    : "no older messages were excluded";
  return `${included} included (window ${history.window_limit ?? "?"}), ${older}`;
}

/**
 * Expandable sections that exist in THIS payload, in stable display order.
 * Empty parts (no retrieval, no history) are omitted instead of shown empty.
 */
export function snapshotSections(snapshot: ModelRequestSnapshot | null): ModelRequestSection[] {
  const sections: ModelRequestSection[] = [];
  const messages = requestMessages(snapshot);
  if (messages.length > 0) {
    sections.push({
      id: "messages",
      title: "Messages sent",
      summary: `${messages.length} message${messages.length === 1 ? "" : "s"} (system, user, assistant in send order)`,
    });
  }
  const retrieval = snapshot?.assembly?.retrieval;
  if (retrieval?.sources?.length) {
    const truncated = retrieval.sources.filter((s) => s.truncated).length;
    sections.push({
      id: "retrieval",
      title: "Retrieved sources",
      summary: `${retrieval.sources.length} of top_k ${retrieval.top_k ?? "?"} chunks${truncated ? `, ${truncated} truncated to ${retrieval.source_text_truncated_to_chars ?? "?"} chars` : ""}`,
    });
  }
  const graph = snapshot?.assembly?.graph_context;
  if (graph && ((graph.entities?.length ?? 0) > 0 || (graph.expanded?.length ?? 0) > 0)) {
    sections.push({
      id: "graph",
      title: "Graph context",
      summary: `${graph.entities?.length ?? 0} entities, ${graph.expanded?.length ?? 0} expanded`,
    });
  }
  const history = snapshot?.assembly?.history;
  if (history?.entries?.length) {
    sections.push({ id: "history", title: "Included history", summary: windowNote(snapshot) });
  }
  const settings = snapshot?.generation_settings;
  if (settings && Object.keys(settings).length > 0) {
    sections.push({
      id: "settings",
      title: "Generation settings",
      summary: Object.entries(settings)
        .filter(([, value]) => value !== undefined)
        .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
        .slice(0, 3)
        .join(" · "),
    });
  }
  if (snapshot?.request?.url) {
    sections.push({
      id: "transport",
      title: "Transport",
      summary: `${snapshot.request.method ?? "POST"} ${snapshot.request.url}`,
    });
  }
  sections.push({ id: "privacy", title: "Privacy & retention", summary: "What is excluded and how long it is kept" });
  return sections;
}

/** Honest status wording: sent vs failed vs cancelled vs unavailable. */
export function statusLabel(snapshot: ModelRequestSnapshot | null): string {
  if (!snapshot) return "No captured request";
  if (snapshot.status === "sent") return "Sent to model";
  if (snapshot.status === "failed") return "Request failed";
  if (snapshot.status === "cancelled") return "Stopped before completion";
  return `What was sent (${snapshot.status ?? "unknown status"})`;
}

/** Tailwind text/border tone pair for the status badge. */
export function statusTone(snapshot: ModelRequestSnapshot | null): string {
  if (!snapshot) return "text-app-muted border-app-border";
  if (snapshot.status === "sent") return "text-verified border-verified/40";
  if (snapshot.status === "failed") return "text-rust border-rust/40";
  if (snapshot.status === "cancelled") return "text-amber border-amber/40";
  return "text-app-muted border-app-border";
}

export function providerLabel(snapshot: ModelRequestSnapshot | null): string {
  const provider = snapshot?.provider;
  if (!provider?.model) return "Unknown model";
  return `${provider.provider ?? "unknown provider"} / ${provider.model}`;
}

/** Clearly estimated token total for the captured request. */
export function estimatedTokensLabel(snapshot: ModelRequestSnapshot | null): string {
  const counts = snapshot?.token_counts;
  if (!counts || typeof counts.total !== "number" || counts.total <= 0) return "no token estimate";
  return `~${counts.total.toLocaleString("en-US")} tokens (estimate)`;
}

/** Exact JSON the server captured — copy/download use this verbatim. */
export function snapshotPayloadText(snapshot: ModelRequestSnapshot): string {
  return JSON.stringify(snapshot, null, 2);
}

export function snapshotFilename(snapshot: ModelRequestSnapshot): string {
  return `model-request-${snapshot.request_id}.json`;
}

/** Trigger a JSON download of the sanitized snapshot in the browser. */
export function downloadSnapshot(snapshot: ModelRequestSnapshot): void {
  if (typeof document === "undefined") return;
  const blob = new Blob([snapshotPayloadText(snapshot)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = snapshotFilename(snapshot);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
