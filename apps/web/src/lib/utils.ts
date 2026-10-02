import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { EntityChunk } from "@/lib/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Collapse the duplicate entity-chunk rows that re-processing a document
 * stacks up (same source content, fresh row ids), without merging two
 * genuinely different sections that happen to share a filename and page.
 *
 * The key is `filename | page | chunk_index`: `chunk_index` is what makes it
 * safe. Re-processing re-chunks deterministically, so a retry reproduces the
 * same `chunk_index` for the same content (and those *do* collapse), while two
 * distinct sections on one page always differ in `chunk_index` (and do not).
 * Keying on `filename | page` alone merged those two cases together.
 */
export function dedupeEntityChunks(chunks: EntityChunk[]): EntityChunk[] {
  const seen = new Set<string>()

  return chunks.filter((chunk) => {
    const indexKey = chunk.chunk_index ?? `id:${chunk.chunk_id}`
    const key = `${chunk.filename}|${chunk.page_number ?? 0}|${indexKey}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
