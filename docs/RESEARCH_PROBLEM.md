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

**Pinned / Protected knowledge (2026-09-03 proposal):** Important facts can be marked `is_pinned` (`pinned_by/at/reason`, owner/editor only via `project_members`, audit-logged). Pinned edges are **exempt from auto-repair on staleness** (`valid_until` expiry only flags for visibility, never auto-retires). On **conflict** (same `(source,target)` incompatible `relation_type`) a pinned edge never auto-supersedes — it creates `knowledge_health_checks {requires_review}` and prompts the user once (`Keep pinned / Overwrite pinned / Keep both disputed`); only explicit `Accept` mutates (`superseded_by` + `last_validated_at`). See `docs/TODO.md §2.23`.

Evidence-backed trust is central: every answer sentence should point to a doc part (page/section/chunk + sentence span), not just a block citation — see trust discussion. See `CONTEXT.md` citation glossary and `services/chat.py` citation flow for current block-level baseline.

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

1. Map what temporal-KG, GraphRAG, and KG-agent-memory papers handle individually vs what breaks when heterogeneity + conflict + staleness occur together. (Core set: Docs2KG, GraphRAG/KG-RAG, Zep/Graphiti, TempAgent, Jarnac 2025 survey, FactGenius, Kolli hybrid, TempQA/MemoTime — see §11 References — recent audit provided URLs.)
2. Define health signals and repair actions precisely (conflict = same entity pair with contradictory relation types? stale = superseded document? invalid = low-confidence extraction with no evidence?) — include `pinned` semantics: pinned exempt from stale auto-retire, conflict requires explicit human Accept.
3. Implement sentence-level evidence linking (`entity_mentions {span_start,span_end,sentence_text}` + `relationship_evidence` M2M) and dual-chunking quality comparison (fixed vs structure-aware) before claiming embedding/structure novelty — see trust discussion. (`docs/TODO.md §2.24`)
4. Build the retrieval eval harness (`TODO §3.2`) and health benchmark fixture (`TODO §3.6` — 20–30 controlled docs: update/contradiction/stale/duplicate/uncertain + 15–20 QA pairs; baselines `plain RAG vs GraphRAG vs +health`; metrics `recall@k, citation precision, contradiction P/R, factual accuracy Δ`) — without it, no claim about reliability is measurable.
5. Implement pinned/protected flow + health scanner + RAG verification gate (`docs/TODO.md §2.23, §2.27–§2.28`) with periodic `asyncio.Task` scanner and dashboard `Requires Review` inbox; guard against over-pinning (>5% warning, `pinned_reason` required).

---

## 10. How This Relates to Other Docs

* **Build scope →** `BUILD_BRIEF.md` (_locked, see `docs/surfaces.md`)
* **Verified spec →** `docs/SPEC.md` (authoritative spec vs code)
* **How it works →** `docs/HOW_IT_WORKS.md`
* **What's left →** `docs/TODO.md`
* **Domain glossary →** `CONTEXT.md`
* **ADRs →** `docs/adr/001` (Postgres+NetworkX), `002` (single Chroma collection), `003` (Supabase Auth), `004` (MCP spec)

This document does not change build scope — it frames the inquiry that justifies and tests it.

---

## 11. References — Core Papers from Recent Audit (with URLs)

Direct mapping to your audit table “What has already been solved?” — use this as the literature base; see TODO `§2.22` for how they combine into the research gap.

| # | Paper | What it solves | URL |
|---|---|---|---|
| 1 | **Zep: A Temporal Knowledge Graph Architecture for Agent Memory (2025)** — Graphiti, temporal KG as persistent agent memory. Reports 94.8% vs 93.4% on DMR, up to 18.5% on LongMemEval. | KG as agent memory | https://doi.org/10.48550/arXiv.2501.13956 |
| 2 | **Uncertainty Management in the Construction of Knowledge Graphs: A Survey — Jarnac et al., 2025** — uncertain information & conflicts between heterogeneous sources, reconciliation/alignment/fusion. | KG uncertainty | https://drops.dagstuhl.de/entities/document/10.4230/TGDK.3.1.3 |
| 3 | **FactGenius (2024)** — KG evidence verification via LLM prompting + fuzzy relation matching. | KG fact verification | https://aclanthology.org/2024.fever-1.30/ |
| 4 | **Hybrid Fact-Checking that Integrates KG, LLM & Search Agents — Kolli et al., 2025** — KG retrieval → LLM classification → web-search fallback, F1 0.93 on FEVER (supported/refuted). | KG + LLM + search fallback | https://aclanthology.org/2025.winlp-main.19/ |
| 5 | **Time-aware ReAct Agent for Temporal KGQA (TempAgent, 2025)** — temporal constraints in retrieval for time-sensitive KG QA. | Temporal KG reasoning | https://aclanthology.org/2025.findings-naacl.334/ |
| 6 | **TempQA: An LLM-based Framework for Temporal KGQA (2026)** — zero-shot LLM temporal KG QA for evolving facts. | Temporal KG QA | https://www.sciencedirect.com/science/article/pii/S095070512502026X |
| 7 | **Leveraging Temporal Validity of Rules via LLMs (2025)** — temporal validity in evolving KG reasoning. | Temporal validity | https://www.sciencedirect.com/science/article/pii/S0950705125011396 |
| 8 | **MemoTime (2025)** — temporal KG + memory + continual reasoning. | Temporal + memory | https://www.researchgate.net/publication/402295149_Uncertainty_Management_in_the_Construction_of_Knowledge_Graphs_A_Survey — *note: Jarnac survey link duplicated in audit; MemoTime search via OpenAlex/Semantic Scholar recommended for canonical DOI* |
| 9 | **Docs2KG** | Documents → KG extraction | https://arxiv.org/abs/2404.03084 *(audit placeholder — add exact venue/version you cited)* |
| 10 | **GraphRAG / KG-RAG** | Graph-enhanced retrieval & grounding | https://arxiv.org/abs/2404.16130 (GraphRAG), https://arxiv.org/abs/2311.01714 (KG-RAG) *(audit placeholders — replace with your cited versions)* |

> **Usage note for 9–10:** Docs2KG / GraphRAG URLs above are the commonly cited arXiv versions — confirm against your original audit notes and replace if you cited a different venue. 1–7 are exactly the URLs from your audit (UTM stripped). Do not claim novelty on any single row — novelty is the *joint* health mechanism (`TODO §2.22` diagram) and `pinned` conflict-only repair (`TODO §2.23`).
