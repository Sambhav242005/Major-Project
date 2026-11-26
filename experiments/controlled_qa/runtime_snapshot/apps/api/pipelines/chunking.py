"""Text chunking — split documents into ~600-token chunks with ~80 token overlap."""

import tiktoken


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))


def chunk_text(
    text: str,
    max_tokens: int = 600,
    overlap_tokens: int = 80,
    page_number: int | None = None,
) -> list[dict]:
    """Split text into chunks by token count with overlap.

    Returns list of dicts with 'text', 'token_count', 'page_number'.
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return [
            {
                "text": text,
                "token_count": len(tokens),
                "page_number": page_number,
            }
        ]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_decoded = encoding.decode(chunk_tokens)

        chunks.append({
            "text": chunk_text_decoded,
            "token_count": len(chunk_tokens),
            "page_number": page_number,
            "chunk_index": chunk_index,
        })

        chunk_index += 1
        start += max_tokens - overlap_tokens

    return chunks


def chunk_pages(pages: list[dict], max_tokens: int = 600, overlap_tokens: int = 80) -> list[dict]:
    """Chunk a list of pages (each with 'text' and 'page_number').

    Handles cross-page boundaries by concatenating small pages.
    """
    all_chunks = []
    buffer = ""
    buffer_page = None

    for page in pages:
        page_text = page.get("text", "").strip()
        page_num = page.get("page_number")

        if not page_text:
            continue

        if buffer:
            combined = buffer + "\n\n" + page_text
        else:
            combined = page_text
            buffer_page = page_num

        # Check if combined text exceeds max_tokens
        combined_tokens = count_tokens(combined)
        if combined_tokens > max_tokens and buffer:
            # Flush buffer as a chunk
            buffer_tokens = count_tokens(buffer)
            all_chunks.append({
                "text": buffer,
                "token_count": buffer_tokens,
                "page_number": buffer_page,
            })
            buffer = page_text
            buffer_page = page_num
        else:
            buffer = combined

        # If single page exceeds max_tokens, chunk it
        if count_tokens(buffer) > max_tokens:
            page_chunks = chunk_text(buffer, max_tokens, overlap_tokens, buffer_page)
            all_chunks.extend(page_chunks)
            buffer = ""
            buffer_page = None

    # Flush remaining buffer
    if buffer.strip():
        all_chunks.append({
            "text": buffer,
            "token_count": count_tokens(buffer),
            "page_number": buffer_page,
        })

    # Add chunk indices
    for i, chunk in enumerate(all_chunks):
        chunk["chunk_index"] = i

    return all_chunks
