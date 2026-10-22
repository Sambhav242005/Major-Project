# Controlled document QA experiment

This supplement exposes the standalone experiment behind the AKGB controlled
evaluation. It is separate from the production chat UI. It contains the verifier,
benchmark generator, synthetic sources, evaluator-only annotations, original
outputs, configuration and offline reproduction tools. Manuscripts, reference
papers, context files, personal review worksheets and database/vector-store
binaries are excluded.

## What was actually evaluated

- **A_vector:** existing vector retrieval, eight source excerpts.
- **B_graph:** the same evidence plus existing entity descriptions and one-hop
  graph descriptions. Graph expansion does not retrieve extra evidence chunks.
- **C_verified:** B's reused candidate plus one model review, explicit metadata
  eligibility, controlled scalar parsing and exact quotation/citation checks.

The source corpus is fictional, deliberately contains incorrect statements, and
uses explicit metadata and repeated sentence forms. It is a controlled benchmark,
not an independent natural-document test. The literal parser matches this
grammar. Its reported gain does not establish general document QA superiority.
The verifier is research-only; it is not wired into the production chat route and
does not repair persistent graph facts. Models were pretrained, not fine-tuned.

The 24 scenario families contain 96 sources, 120 questions, 272 assertions and
212 candidate assertion pairs. Six development families provide 30 questions;
18 held-out families provide 90 questions. All source documents produced one chunk
in the recorded run. Splits are isolated at family and application project level.

`benchmark/raw/<split>/` is the **only** indexable corpus. `benchmark/private/`
means evaluator-only, not confidential: it contains published answer keys,
annotations and cached neutral prose. Never ingest it or pass it to answering
models. Gold labels become available only to scoring after inference. Publishing
the test set means future reruns are reproductions, not newly untouched tests.

## Offline reproduction: no installation or running models

Run these commands from the repository root with Python 3.11 or later:

```sh
python experiments/controlled_qa/reproduce.py audit
python experiments/controlled_qa/reproduce.py replay --output output/research_replay_01
python experiments/controlled_qa/reproduce.py rebuild-benchmark --output output/rebuilt_benchmark_01
python -m unittest discover -s experiments/controlled_qa -p test_reproduce.py -v
python -m unittest discover -s apps/api/scripts -p test_research_benchmark.py -v
```

Choose a **new** replay output directory. Existing outputs are never overwritten.
No model, HTTP endpoint, .env, SQL database or Chroma store is accessed. The tool
executes the original scorer's selected function definitions in an offline
namespace, avoiding application imports that initialize settings or database
engines. It does not replace the original scoring algorithm with a new metric.

Replay recomputes all three per-question score files, aggregate metrics, paired
family-bootstrap intervals and the AI grading summary. It applies the documented
cost erratum and checks equality with every retained score, including costs.
The bootstrap uses 10,000 paired family resamples with seed 26014; the 18 families,
not 90 independent questions, are the resampling units.

The optional rebuild regenerates all source facts and gold annotations from the
generator plan and retained neutral prose cache, with network generation disabled.
It verifies the original dataset digest and all 96 source byte hashes. It does
not fabricate a human acceptance receipt for the newly created workspace.

`publication_manifest.json` checks source-code hashes after CRLF-to-LF
canonicalization; this handles Git line endings without changing policy. Frozen
traces and benchmark files are checked byte-for-byte. Original code byte hashes
remain in `frozen/experiment_freeze.json`. The publication replaces two workstation
paths in that manifest with `${REPO}` and removes identities/private links from the
dataset summary; these transformations and original export hashes are disclosed.
Hashes bind retained artifacts, but do not independently establish execution
dates, review independence or the scientific validity of annotations.

Deployment and its review later changed `apps/api/pipelines/llm_client.py`,
`apps/api/pipelines/embeddings/embedding_function.py` and
`apps/api/services/chat/streaming.py`. The release OCR fix also changed
`apps/api/pipelines/parser.py`, whose original published bytes are archived too. Their exact original bytes
from commit `c725d63` are retained under `runtime_snapshot/`, with the same
repository-relative paths. Because the manifest also hashes the original
`experiments/controlled_qa/README.md`, `reproduce.py` and `test_reproduce.py`, their
exact published versions are archived there too. Audit checks **only these seven
explicit snapshot paths** against the unchanged publication-manifest hashes;
every other path retains its original check. Current audit/replay tooling and
documentation evolve separately from those archived published versions. Frozen
traces, metrics and manifest hashes are unchanged. Offline replay uses the
original traces and scorer, not the deployed model adapters.

## Retained results and new diagnostics

Normalized accuracy requires an exact normalized set of requested values **and**
the expected answerability status. Every failed execution is incorrect. This
metric does not judge every extra statement in answer prose.

| Diagnostic | A | B | C |
|---|---:|---:|---:|
| Original primary outcome, 90 questions | 45/90 (50.0%) | 41/90 (45.6%) | 52/90 (57.8%) |
| Exclude insufficient cases, 75 questions | 30/75 (40.0%) | 26/75 (34.7%) | 37/75 (49.3%) |
| Normally answerable only, 60 questions | 29/60 (48.3%) | 26/60 (43.3%) | 31/60 (51.7%) |
| Exploratory same-model AI whole-answer grading | 69/90 (76.7%) | 65/90 (72.2%) | 58/90 (64.4%) |

The subset diagnostics are **post hoc** and do not replace the original primary
outcome. C minus A is +7.8 percentage points, with a family-bootstrap 95% interval
of **−2.2 to +18.9 points**, including zero. C minus B is +12.2 points, with an
interval of +1.1 to +26.7 points. These results support a bounded controlled-study
finding, not a definitive superiority claim over the strongest baseline.

| Category (15 questions each) | A correct | B correct | C correct |
|---|---:|---:|---:|
| Distributed information | 5 | 5 | 5 |
| Temporal applicability | 6 | 3 | 8 |
| Draft versus approved | 6 | 5 | 3 |
| Unresolved disagreement | 1 | 0 | 6 |
| Scope differences and copies | 12 | 13 | 15 |
| Insufficient evidence | 15 | 15 | 15 |

The unresolved-status precision/recall for C is 100%/**40%**. This is question-level
status detection, not pair-level contradiction detection. All systems correctly
handle the 15 insufficient-information cases, so these should be distinguished
from the more difficult disputed cases. Macro evidence-group coverage is 66%.

### Failure and approval-rule audit

All 16 C failures are retained in their original traces and primary denominator.
The first reported validation failures are 12 positive answers without the
required value/evidence set, two values absent from quotations, one invalid source
number and one reference missing from the answer. These are first failures, not
mutually exclusive explanations of all defects in each response. The post-hoc
analysis also checks missing fields, quotation existence and proposal agreement
with the original values/status labels; it is not independent semantic judgment.
None of the 16 rejected raw proposals matches both the required gold values and
status. Relaxing quotation/citation checks alone therefore would not make those
unchanged proposals correct under the original primary metric.

Failures occur in distributed (3), temporal (5) and draft/approved (8) questions.
The explicit governance sentence is absent from the retrieved excerpts for **all
15 draft questions**. The literal path therefore cannot apply its rule-dependent
draft exclusion; retained mixed approvals send cases to the fallible model path.
This is a trace-supported explanation of the regression, not a controlled causal
ablation. It also exposes a coverage limitation: retrieving required value
assertions does not necessarily retrieve the governing eligibility rule.

The four A-correct/C-wrong draft cases are F011-Q3, F011-Q4, F012-Q3 and F012-Q4;
F011-Q1 changes from A-wrong to C-correct. Their net difference is three cases.
The machine-readable case audit is in `analysis/posthoc_analysis.json` and is
regenerated by replay. No frozen answer is repaired or silently replaced.

### Cost accounting erratum

The frozen C recorder omitted reused B-candidate token usage on failed C rows,
and counted retrieval overhead twice in their logical latency. Original traces
remain unchanged. `frozen/before_cost_accounting_correction/` retains the earlier
derived summaries, while `runtime_accounting_correction.json` documents the fix.
For every C row the corrected token cost is B candidate plus C review; failed
logical times remove one duplicate retrieval term. Offline replay reapplies the
correction idempotently. C's corrected median latency is 6.182 seconds and its
mean prompt usage is 3654.589 tokens. Serial A/B/C order and caching limit runtime
comparisons. The erratum changes no values, statuses, citations or accuracy labels.

## Fresh model inference in a clean checkout

Offline replay above is verified. Full fresh ingestion/model inference is a
different operation requiring the original dependencies and models; it is not
claimed to have been rerun as part of packaging this supplement. Floating model
tags, extraction behavior and platform differences may change results. Compare
digests with `frozen/model_manifest.json` before claiming a matched reproduction.

Use a separate clean checkout without an existing `output/research_benchmark/`.
The original runner deliberately uses that isolated path and never the live app
database. This preparation command refuses to overwrite existing research files:

For fresh inference, use a separate checkout at frozen-runtime revision `c725d63`
(for example, `git worktree add --detach ../akgb-frozen-runtime c725d63`). Do not
overwrite the deployed application's files. The current preparation command
refuses changed live adapters rather than silently recording deployment code as
the original experimental runtime. The snapshots preserve inspectable source;
they do not automatically replace imports in the production application.

```sh
python experiments/controlled_qa/reproduce.py prepare-inference
python -m venv .venv
```

Activate `.venv` using your shell, then install the recorded inference environment:

```sh
python -m pip install -r experiments/controlled_qa/requirements-inference.txt
```

The complete original Windows/Python 3.11 environment is retained in
`frozen/requirements-research.txt`. The install file only makes the Windows-only
pywin32 dependency conditional. This is a captured environment, not a claimed
minimal cross-platform dependency set. No model weights are committed.

The operator must start and manage Ollama. With Ollama already running, prepare
the recorded model alias and embedding model:

```sh
ollama pull qwen2.5:7b
ollama pull nomic-embed-text:v1.5
ollama create akgb-qwen2.5-7b -f experiments/controlled_qa/Modelfile
```

The recorded endpoint is `http://127.0.0.1:11434/v1`; no local key is required.
Chat/extraction use `akgb-qwen2.5-7b`; embeddings use the existing OpenAI-compatible
provider and `nomic-embed-text:v1.5`, 768 dimensions, without prefix additions.
The alias sets seed 26014 and context 8192. Answer/review generation uses
temperature zero and output limit 1800. Existing extraction uses temperature 0.1
and limit 2000. Production UI generation has separate settings.

```sh
python apps/api/scripts/application_benchmark.py ingest --split dev
python apps/api/scripts/application_benchmark.py ingest --split test
python apps/api/scripts/application_benchmark.py run --split dev
python apps/api/scripts/application_benchmark.py run --split test
python experiments/controlled_qa/reproduce.py replay --input-root output/research_benchmark/application --output output/new_inference_scores_01
```

Preparation copies the published frozen protocol with explicitly disclosed path
and working-tree line-ending resolution. Do not call `freeze` to invent a new
human review receipt or reinterpret a reproduction as an untouched evaluation.
No backend or frontend server is needed. The runner can resume completed rows;
failed rows remain recorded, and partial ingestion requires explicit diagnosis.
The development record describes four iterations, with final development traces
published here; preliminary development archives remain in the local archive.

## Human answer review: the remaining validity check

One source/gold reviewer accepted the dataset. That is different from human
grading of generated answers. The AI judge shares the generator's model family,
and its opposite whole-answer ranking remains unresolved. Neither an additional
AI judge nor this mechanical replay supplies independent human validation.

```sh
python experiments/controlled_qa/reproduce.py human-packet --output output/human_audit_01
```

Send **only** the generated `Reviewer_Packet.zip` to a human reviewer. It contains
30 questions (five/category, all 18 test families), 90 shuffled anonymous answers,
numbered source excerpts, complete scenario sources, all 72 searchable test
sources and an empty grading CSV. The selection rule is fixed independently of
system success. Keep `organizer_only/` away from the reviewer until grades return.

The human records correctness, omissions, unsupported claims, citation support
and reasons. A reviewer who did not implement the answering system is preferable;
disclose prior source familiarity and author involvement. If two people review,
they should grade separately before adjudication. Label the result a post-hoc,
model-label-blinded audit; answer style may reveal configurations. No human grades
or agreement estimate are claimed by this supplement. Review returns and reviewer
identities stay local unless separately authorized for publication.

## Verification scope

Targeted backend checks: `tests/test_audit.py`, `tests/test_chat.py` and
`tests/test_evidence_gate.py`. Set a local SQLite `DATABASE_URL` before collecting
them if your app .env points at PostgreSQL. No full frontend or production
authentication certification is implied. The small audit-service UUID fix is
included because the actual in-process chat pilot exposed that persistence bug.
