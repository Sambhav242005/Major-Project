# Context: AI Knowledge Graph Builder

## Domain Glossary

| Term | Definition |
|------|-----------|
| **Document** | A raw file (PDF/DOCX/TXT/image) uploaded by a user. Has a lifecycle: pending → processing → processed/failed. Stored in Supabase Storage; metadata in Postgres. |
| **Chunk** | A ~600-token segment of a Document, retaining page number. Embedded into ChromaDB for semantic search. Linked back to its source Document via `document_chunks` table. |
| **Entity** | A named thing extracted from documents: person, organization, concept, location, date. Unique per (project_id, name, type). |
| **Entity Mention** | A specific occurrence of an Entity in a Chunk. Links entity to document, chunk, mention text, and confidence score. |
| **Relationship** | A typed connection between two Entities (e.g., "works_at", "founded_by"). Extracted from document context. Has confidence and source document. |
| **Knowledge Graph** | The network of Entities and Relationships within a Project. Stored as rows in Postgres, traversed in-memory via NetworkX subgraphs. |
| **Project** | Top-level container. All documents, entities, relationships, chat sessions, and agents belong to a Project. Users access Projects via Project Memberships. |
| **Project Member** | A user with a role (owner/editor/viewer) on a Project. Row-level security scopes all data access to project membership. |
| **Chat Session** | A conversation thread within a Project. Contains user and assistant messages with citations. |
| **Citation** | A reference from an assistant message to a specific chunk/document/page. Stored as JSON in `chat_messages.citations`. |
| **Agent** | An automated task runner backed by LangGraph. Has a type, config, and produces Tasks with step-by-step traces. |
| **Agent Task** | A single execution of an Agent. Contains input, output, status, and a LangGraph trace for UI visualization. |
| **MCP Connection** | An external integration. Sender = this platform exposed as MCP server. Receiver = this platform calling external MCP servers (e.g., Google Meet). |
| **Ingestion Pipeline** | The async flow: parse → chunk → embed → extract entities/relations. Triggered on document upload. |
| **Retrieval Pipeline** | The RAG flow: embed query → Chroma search → NetworkX hop expansion → prompt assembly → LLM stream. |

## Key Relationships

```
Project 1──* Document 1──* Chunk *──1 Entity Mention *──1 Entity
                                  Entity 1──* Relationship *──1 Entity
Project 1──* Chat Session 1──* Chat Message
Project 1──* Agent 1──* Agent Task
Project 1──* MCP Connection
```

## Architectural Decisions

- Postgres + NetworkX for graph (not Neo4j) — see `docs/adr/001-supabase-over-neo4j.md`
- Single ChromaDB collection with metadata filtering — see `docs/adr/002-chromadb-single-collection.md`
- Supabase Auth for authentication — see `docs/adr/003-supabase-auth.md`

## Design System

- Colors: paper (#F5F3EE), ink (#16213E), slate (#6B7280), amber (#C9862B), verified (#2F6E63), rust (#B4432F)
- Fonts: Fraunces (display), Inter (body), IBM Plex Mono (utility/citations)
- Voice: name things by user control, not system internals. "Upload documents" not "Trigger ingestion pipeline"
