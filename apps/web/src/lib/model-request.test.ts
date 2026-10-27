import { describe, expect, it } from "vitest";
import {
  downloadSnapshot,
  estimatedTokensLabel,
  providerLabel,
  requestMessages,
  snapshotFilename,
  snapshotPayloadText,
  snapshotSections,
  statusLabel,
  statusTone,
  type ModelRequestSnapshot,
} from "./model-request";

const base: ModelRequestSnapshot = {
  schema: "model_request.snapshot.v1",
  request_id: "req-1",
  status: "sent",
  provider: {
    provider: "openai",
    model: "selected-model",
    endpoint: "https://api.groq.com/openai/v1/chat/completions",
    request_shape: "chat_completions",
  },
  request: {
    method: "POST",
    url: "https://api.groq.com/openai/v1/chat/completions",
    headers: { Authorization: "(excluded from snapshot)", "Content-Type": "application/json" },
    body: {
      messages: [
        { role: "system", content: "You are a knowledgeable assistant." },
        { role: "user", content: "Sources:\n[Source 1] Document: report.pdf, Page: 3\n…\nQuestion: Summarize" },
      ],
    },
  },
  generation_settings: { stream: true, temperature: 0.4 },
  token_counts: {
    estimate: true,
    method: "chars/4 rough estimate",
    total: 1234,
    by_message: [],
    request_body_characters: 900,
  },
  assembly: {
    flow: "chat.send_message",
    history: {
      window_limit: 20,
      rows_returned_by_window: 3,
      included_entries: 2,
      assistant_clipped_to_chars: 200,
      may_exclude_older_messages: false,
      entries: [{ role: "assistant", content: "…", truncated: true }],
    },
    retrieval: {
      top_k: 8,
      query: "Summarize",
      source_count: 1,
      source_text_truncated_to_chars: 800,
      sources: [{
        index: 1, chunk_id: "doc1_chunk_0", document_id: "doc", filename: "report.pdf",
        page_number: 3, text: "chunk text", truncated: true, original_characters: 900,
      }],
      truncation_decisions: "per-source text clipped",
    },
    graph_context: {
      entities: [{ name: "Northwind", type: "org", description: "supplier" }],
      entities_shown_in_prompt: 1,
      entities_omitted: 0,
      expanded: [],
      expanded_shown_in_prompt: 0,
      expanded_omitted: 0,
    },
    attachments: [],
    tools: { present: false },
  },
};

describe("model request snapshot helpers", () => {
  it("lists sections that exist, in stable order", () => {
    const sections = snapshotSections(base).map((section) => section.id);
    expect(sections).toEqual([
      "messages", "retrieval", "graph", "history", "settings", "transport", "privacy",
    ]);
  });

  it("keeps the messages section even when nothing else was assembled", () => {
    const minimal: ModelRequestSnapshot = {
      request_id: "req-2",
      request: { body: { messages: [{ role: "user", content: "Hi" }] } },
    };
    const sections = snapshotSections(minimal).map((section) => section.id);
    expect(sections).toEqual(["messages", "privacy"]);
    expect(requestMessages(minimal)).toEqual([{ role: "user", content: "Hi" }]);
  });

  it("summarizes retrieval truncation", () => {
    const sections = snapshotSections(base);
    const retrievalSection = sections.find((s) => s.id === "retrieval");
    expect(retrievalSection?.summary).toContain("1 of top_k 8");
    expect(retrievalSection?.summary).toContain("truncated to 800 chars");
  });

  it("summarizes history window honestly", () => {
    const historySection = snapshotSections(base).find((s) => s.id === "history");
    expect(historySection?.summary).toContain("2 included (window 20)");
    expect(historySection?.summary).toContain("no older messages were excluded");
  });

  it("reports a window that may exclude older messages", () => {
    const snapshot: ModelRequestSnapshot = {
      ...base,
      assembly: {
        ...base.assembly!,
        history: { ...base.assembly!.history!, may_exclude_older_messages: true },
      },
    };
    const summary = snapshotSections(snapshot).find((s) => s.id === "history")?.summary;
    expect(summary).toContain("older messages beyond the window may be excluded");
  });

  it("summarizes generation settings observed in the request body", () => {
    const settingsSection = snapshotSections(base).find((s) => s.id === "settings");
    expect(settingsSection?.summary).toContain("stream: true");
    expect(settingsSection?.summary).toContain("temperature: 0.4");
  });

  it("labels statuses accurately — sent, failed, cancelled, missing", () => {
    expect(statusLabel(base)).toBe("Sent to model");
    expect(statusLabel({ ...base, status: "failed" })).toBe("Request failed");
    expect(statusLabel({ ...base, status: "cancelled" })).toBe("Stopped before completion");
    expect(statusLabel(null)).toBe("No captured request");
    expect(statusLabel({ ...base, status: null })).toBe("What was sent (unknown status)");
    expect(statusTone({ ...base, status: "failed" })).toContain("rust");
    expect(statusTone({ ...base, status: "cancelled" })).toContain("amber");
    expect(statusTone(base)).toContain("verified");
  });

  it("describes provider and clearly-labeled token estimates", () => {
    expect(providerLabel(base)).toBe("openai / selected-model");
    expect(estimatedTokensLabel(base)).toBe("~1,234 tokens (estimate)");
    expect(estimatedTokensLabel(null)).toBe("no token estimate");
    expect(statusLabel({ ...base, status: "failed", failure_reason: "provider returned HTTP 500" }))
      .toBe("Request failed");
  });

  it("serializes the captured payload verbatim for copy/download", () => {
    expect(snapshotPayloadText(base)).toBe(JSON.stringify(base, null, 2));
  });

  it("names downloads after the captured request", () => {
    expect(snapshotFilename(base)).toBe("model-request-req-1.json");
    expect(() => downloadSnapshot(base)).not.toThrow();
  });

  it("hides the messages section when the payload carries none", () => {
    const noMessages: ModelRequestSnapshot = { request_id: "req-3", request: { body: {} } };
    const sections = snapshotSections(noMessages).map((s) => s.id);
    expect(sections).toEqual(["privacy"]);
  });
});
