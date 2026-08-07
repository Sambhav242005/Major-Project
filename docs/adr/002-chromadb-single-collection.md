# ADR-0002: Single ChromaDB Collection with Metadata Filtering

## Status
Accepted

## Context
ChromaDB stores document embeddings for semantic search. Multiple projects need isolation — one project's search must never return another project's chunks.

## Decision
Use a single `knowledge_base` collection with metadata filtering (`where={"project_id": ...}`) instead of one collection per project.

## Consequences

### Positive
- Simpler to operate — one collection to manage
- Chroma's metadata `where` filters make per-project isolation trivial
- Cross-project queries possible if ever needed (admin, analytics)

### Negative
- All projects share one collection's index (slightly less cache locality)
- Collection deletion affects all projects

### Risks
- Acceptable at MVP scale; metadata filtering performance is well-tested in ChromaDB
