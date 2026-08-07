# ADR-0001: Supabase + Postgres over Neo4j for Graph Storage

## Status
Accepted

## Context
The original proposal specified Neo4j for graph storage. The project needs to store entities and relationships and support multi-hop traversal queries. Neo4j is a dedicated graph database with Cypher query language.

## Decision
Use PostgreSQL (via Supabase) with NetworkX for in-memory traversal instead of Neo4j.

## Consequences

### Positive
- No additional database service to operate (Postgres already used for relational data)
- Entities and relationships are normal rows — easy to query, back up, explain in viva
- NetworkX provides full graph traversal in-memory for subgraph sizes realistic at MVP scale (few thousand entities)
- Migration path: relationship table is already shaped so a future migration script could load into Neo4j

### Negative
- No native graph query language (Cypher)
- Multi-hop queries require loading subgraph into NetworkX first
- At very large scale (>100k entities), in-memory traversal may become a bottleneck

### Risks
- Mitigated by project-scoped subgraph loading (never load entire graph)
- Acceptable for semester MVP scope
