import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { EntityChunk } from "@/lib/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Collapse the duplicate entity-chunk rows that re-processing a document
 * stacks up (same source content, fresh row ids), without merging two
 * genuinely different sections.
 *
 * The key is `document_id | chunk_index`. `chunk_index` is assigned by the
 * chunker as a position within one document's ordered chunk list
 * (`pipelines/chunking.py`), so it identifies a section *inside* a document and
 * must be scoped by `document_id` — two documents both called `report.pdf`
 * produce the same indices. Keying on `filename` merged them.
 *
 * Re-processing the same bytes re-chunks deterministically and reproduces the
 * same index, so retries collapse. A re-upload of *revised* bytes shifts every
 * index and legitimately surfaces as new chunks rather than being folded into
 * the previous version.
 */
export function dedupeEntityChunks(chunks: EntityChunk[]): EntityChunk[] {
  const seen = new Set<string>()

  return chunks.filter((chunk) => {
    const key = `${chunk.document_id}|${chunk.chunk_index}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
