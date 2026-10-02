import { describe, expect, it } from "vitest";
import { dedupeEntityChunks } from "@/lib/utils";
import type { EntityChunk } from "@/lib/types";

function chunk(overrides: Partial<EntityChunk> & { document_id: string; chunk_index: number }): EntityChunk {
  return {
    chunk_id: `${overrides.document_id}-${overrides.chunk_index}`,
    text: "text",
    page_number: 1,
    filename: "report.pdf",
    ...overrides,
  };
}

describe("dedupeEntityChunks", () => {
  it("collapses re-processing duplicates that share a document and index", () => {
    // Same document, same chunk_index, fresh row id — a retry of identical bytes.
    const chunks = [
      chunk({ document_id: "doc-a", chunk_index: 0, chunk_id: "row-1" }),
      chunk({ document_id: "doc-a", chunk_index: 0, chunk_id: "row-2" }),
    ];

    expect(dedupeEntityChunks(chunks)).toHaveLength(1);
    expect(dedupeEntityChunks(chunks)[0].chunk_id).toBe("row-1");
  });

  it("keeps distinct sections within one document", () => {
    const chunks = [
      chunk({ document_id: "doc-a", chunk_index: 0 }),
      chunk({ document_id: "doc-a", chunk_index: 1 }),
    ];

    expect(dedupeEntityChunks(chunks)).toHaveLength(2);
  });

  it("keeps same-index chunks from different documents sharing a filename", () => {
    // chunk_index is a position within one document's chunk list, so two
    // documents produce identical indices. Filename alone would merge these.
    const chunks = [
      chunk({ document_id: "doc-a", chunk_index: 0, filename: "report.pdf" }),
      chunk({ document_id: "doc-b", chunk_index: 0, filename: "report.pdf" }),
    ];

    expect(dedupeEntityChunks(chunks)).toHaveLength(2);
  });

  it("does not merge on filename, page, or text alone", () => {
    const chunks = [
      chunk({ document_id: "doc-a", chunk_index: 0, page_number: 7, filename: "a.pdf", text: "one" }),
      chunk({ document_id: "doc-a", chunk_index: 0, page_number: 7, filename: "a.pdf", text: "two" }),
    ];

    // Identical filename/page/index: a genuine retry, so exactly one survives.
    expect(dedupeEntityChunks(chunks)).toHaveLength(1);
  });

  it("returns an empty array unchanged", () => {
    expect(dedupeEntityChunks([])).toEqual([]);
  });

  it("preserves input order", () => {
    const chunks = [
      chunk({ document_id: "doc-a", chunk_index: 2 }),
      chunk({ document_id: "doc-a", chunk_index: 0 }),
      chunk({ document_id: "doc-a", chunk_index: 2, chunk_id: "dup" }),
      chunk({ document_id: "doc-a", chunk_index: 1 }),
    ];

    expect(dedupeEntityChunks(chunks).map((c) => c.chunk_index)).toEqual([2, 0, 1]);
  });
});