# Research Problem — Trust-Based Self-Healing Knowledge System

**Separation:** This document frames the *research inquiry*. `BUILD_BRIEF.md` frames the *semester engineering scope*. `docs/SPEC.md` documents what the system *actually is* verified against code. Do not mix them — see §1.

---

## 1. Project (Build) vs Research (Inquiry) — Keep Them Separate

We have been mixing them together. They are different:

* **Project problem (engineering):** Build a working system that ingests scattered documents and makes knowledge usable. Demo moments in `BUILD_BRIEF.md §1` define "done." Scope-disciplined, semester-bound.
* **Research problem (inquiry):** Understand how that knowledge stays reliable when documents are heterogeneous, changing, and contradictory — and whether a continuously validated system can answer more reliably than conventional RAG.

If we stop at "documents → knowledge graph → chatbot," we have a useful product, not a research contribution. Papers already show KG extraction, GraphRAG, KG agent memory, multi-agent graph reasoning (see research summary). Claiming "we built a KG chatbot" is not defensible.

---

## 2. The Main Project Problem — Fragmented Knowledge

Organizations hold knowledge spread across **PDFs, reports, notes, emails, meeting records, images**.

The deeper problem is not keyword search:

> **Information is fragmented, unstructured, and disconnected, making it difficult for an AI system to understand relationships and use knowledge reliably.**

Traditional search finds words; it does not connect ideas, preserve context, or support follow-ups. The system therefore tries to transform:

```
Scattered Documents
       ↓
PDF / DOCX / TXT / Images / Reports
       ↓
      ????
```

into:

```
                Knowledge Graph
              /       |        \
          Entity    Relation    Evidence
             \        |        /
              \       |       /
               Structured Knowledge
                       ↓
                 AI Agent / LLM
                       ↓
              Grounded Answer (with citations)
```

This is the *project* value — turning scattered files into navigable, structured knowledge.

---

## 3. But That's Not Yet a Research Problem

Building the above in isolation is product engineering. The research starts when we ask what happens **after** 10,000 documents are ingested:

* New document introduces new information.
* Another document contradicts it — now the KG holds conflicts.
* Old information becomes outdated but remains in the graph.
* LLM extraction makes a mistake — incorrect edge enters the KG.
* An agent retrieves that incorrect knowledge and answers confidently.

So the fundamental research problem is:

> **How can an AI system maintain a reliable and continuously evolving knowledge representation when the underlying documents are heterogeneous, incomplete, changing, and potentially contradictory?**

---

## 4. The Self-Healing Idea — Build → Monitor → Verify → Repair

Instead of:

> **Build once → query forever**

investigate:

> **Build → monitor → detect problems → verify → repair → continue**

```
                 Documents
                     ↓
              Knowledge Extraction
                     ↓
              Knowledge Graph
                     ↓
          ┌──────────┴──────────┐
          │                     │
       Querying             Health Check
          │                     │
          │              ┌──────┼──────┐
          │              ↓      ↓      ↓
          │         Conflict  Stale  Invalid
          │         Detection Knowledge Relation
          │              │      │      │
          │              └──────┼──────┘
          │                     ↓
          │              Evidence Check
          │                     ↓
          │               Repair / Reject
          │                     ↓
          └────────────── Knowledge Graph
                              │
                              ↓
                           Agent
                              │
                              ↓
                       Grounded Answer
```

The KG is not assumed correct forever. Key questions: what counts as health/conflict/stale, what triggers a check, what counts as repair (remove edge vs mark disputed vs add evidence).

Evidence-backed trust is central: every answer sentence should point to a doc part (page/section/chunk), not just a block citation — see trust discussion. See `CONTEXT.md` citation glossary and `services/chat.py` citation flow for current block-level baseline.

---

## 5. Where Stateless Architecture Fits — Separate Concern

This is an architectural property, not the primary knowledge problem.

Processing can be stateless:

```
Request 1 → Agent Server A
Request 2 → Agent Server C
Request 3 → Agent Server B
```

Persistent state lives externally:

```
             Stateless Services
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
      Vector DB   Postgres   Storage
        │
        ↓
 Persistent Knowledge
```

This gives scalability and fault tolerance. **Do not claim statelessness as research novelty** — it is a well-established distributed-systems concept. It is an architectural property that lets the knowledge system scale.

---

## 6. Three-Layer Problem Statement

### Layer 1 — Knowledge problem
**Documents are fragmented and unstructured.** Need to transform them into structured knowledge (entities, relations, evidence).

### Layer 2 — Knowledge reliability problem
**Extracted knowledge can become incorrect, contradictory, or outdated.** Need mechanisms to detect and repair.

### Layer 3 — AI interaction problem
**Agents cannot hold the entire organizational knowledge in context.** Need external retrieval with grounded answers.

**Combined research question:**

> **How can we build an AI knowledge system that converts heterogeneous documents into a structured knowledge graph, continuously maintains the reliability of that knowledge as information changes or conflicts, and allows AI agents to retrieve grounded information without requiring the entire knowledge base to reside in their context?**

---

## 7. Hypothesis

> **A knowledge system that maintains evidence-backed, continuously validated knowledge can provide more reliable and grounded answers than a conventional document/vector RAG system when information is conflicting, outdated, or distributed across multiple documents.**

This is testable. It is not yet proven novel — temporal KG memory, schema evolution, GraphRAG etc. exist. Our next job is to find what existing systems do **not** handle well when these problems occur **together**.

### Test sketch — Same documents, two systems

```
                 Same documents
                      │
          ┌───────────┴───────────┐
          ↓                       ↓
     Normal RAG              Our System
          │                       │
          ↓                       ↓
       Answer              Detect conflict
                                  ↓
                            Check evidence
                                  ↓
                             Update KG
                                  ↓
                               Answer
```

**Metrics:** factual accuracy, contradiction detection, stale detection, evidence correctness, citation accuracy, answer quality, retrieval cost, latency. See `BUILD_BRIEF.md §11` retrieval harness (hand-label 15–20 Q/A pairs) — currently missing, see `docs/TODO.md §3.2` — that harness blocks defensible measurement.

---

## 8. What the Current System Already Provides Toward This

* **Ingestion self-heal (partial):** spaCy + LLM extraction, merge/dedup by `(project_id, name, type)`, fallback `co_occurs_with` edges, non-fatal extraction — `pipelines/entity_extraction.py`, `pipelines/ingestion.py`.
* **Trust layer (partial):** block-level citations `citations JSON` in `chat_messages`, `audit_log` writers (PR #2) — not yet sentence-level provenance.
* **Memory/refinement loop (scaffold):** `agent_run_traces` → `agent_skills` via `pipelines/agent_refinement.py` held-in/held-out evals — not yet tied to KG repair.

These are starting points, not validation of the hypothesis.

---

## 9. Next Research Work — Find the Gap

1. Map what temporal-KG, GraphRAG, and KG-agent-memory papers handle individually vs what breaks when heterogeneity + conflict + staleness occur together.
2. Define health signals and repair actions precisely (conflict = same entity pair with contradictory relation types? stale = superseded document? invalid = low-confidence extraction with no evidence?).
3. Implement sentence-level evidence linking and dual-chunking quality comparison (fixed vs structure-aware) before claiming embedding/structure novelty — see trust discussion.
4. Build the retrieval eval harness (`TODO §3.2`) — without it, no claim about reliability is measurable.

---

## 10. How This Relates to Other Docs

* **Build scope →** `BUILD_BRIEF.md` (_locked, see `docs/surfaces.md`)
* **Verified spec →** `docs/SPEC.md` (authoritative spec vs code)
* **How it works →** `docs/HOW_IT_WORKS.md`
* **What's left →** `docs/TODO.md`
* **Domain glossary →** `CONTEXT.md`
* **ADRs →** `docs/adr/001` (Postgres+NetworkX), `002` (single Chroma collection), `003` (Supabase Auth), `004` (MCP spec)

This document does not change build scope — it frames the inquiry that justifies and tests it.
