"""Cohesive chunk batching for LLM extraction."""


def _extract_cohesive_chunks(chunks: list[dict], max_tokens: int = 1200) -> list[dict]:
    """Combine small consecutive chunks for better entity co-occurrence."""
    batches = []
    current_text = ""
    current_chunks: list[dict] = []

    for chunk in chunks:
        text = chunk.get("text", "")
        if len(current_text) + len(text) > max_tokens * 4 and current_text:
            batches.append({
                "text": current_text,
                "chunk_ids": [c.get("id") for c in current_chunks if c.get("id")],
                "page_numbers": list(set(c.get("page_number", 0) for c in current_chunks)),
            })
            current_text = text
            current_chunks = [chunk]
        else:
            current_text += "\n\n" + text if current_text else text
            current_chunks.append(chunk)

    if current_text:
        batches.append({
            "text": current_text,
            "chunk_ids": [c.get("id") for c in current_chunks if c.get("id")],
            "page_numbers": list(set(c.get("page_number", 0) for c in current_chunks)),
        })

    return batches
