"""Inspect the frozen AKGB study without models, services, or third-party packages.

The replay command executes the original scorer's function definitions, with an
offline app namespace. It does not import application settings, read .env, build
an index, or contact an inference endpoint. New analyses are explicitly post hoc.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
from contextlib import redirect_stdout
import hashlib
import html
import importlib.util
import io
import json
from pathlib import Path, PureWindowsPath
import random
import shutil
import statistics
from types import SimpleNamespace
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = HERE / "benchmark"
FROZEN = HERE / "frozen"
NAMES = ("A_vector", "B_graph", "C_verified")
# These deployment adapters changed after the study. Fresh inference must still
# use their original bytes, rather than silently accepting deployment changes.
RUNTIME_SNAPSHOT_FILES = (
    "apps/api/pipelines/llm_client.py",
    "apps/api/pipelines/embeddings/embedding_function.py",
)
RUNTIME_SNAPSHOT = HERE / "runtime_snapshot"
# The manifest also hashes its original tooling/documentation. Retain those
# versions while this inspectable audit tool evolves; never rewrite that manifest.
PUBLICATION_SNAPSHOT_FILES = RUNTIME_SNAPSHOT_FILES + (
    "experiments/controlled_qa/README.md",
    "experiments/controlled_qa/reproduce.py",
    "experiments/controlled_qa/test_reproduce.py",
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path, canonical=False):
    value = path.read_bytes()
    if canonical:
        value = value.replace(b"\r\n", b"\n")
    return hashlib.sha256(value).hexdigest()


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relative_path(value):
    return Path(*PureWindowsPath(value).parts)


def audit():
    manifest = read(HERE / "publication_manifest.json")
    failures = []
    for name, expected in manifest["files"].items():
        path = (RUNTIME_SNAPSHOT if name in PUBLICATION_SNAPSHOT_FILES else REPO) / name
        if not path.is_file() or sha(path, expected["newline_canonicalized"]) != expected["published_sha256"]:
            failures.append(name)
    if failures:
        raise ValueError("Publication integrity check failed: " + ", ".join(failures))
    generator = load_file("frozen_generator", REPO / "apps/api/scripts/research_benchmark.py")
    checked = generator.validate(DATA)
    digest = generator.dataset_content_digest(DATA)
    if digest != read(FROZEN / "experiment_freeze.json")["dataset_content_digest"]:
        raise ValueError("Dataset content digest differs from the original freeze")
    expected_ids = {q["question_id"] for q in rows(DATA / "private/questions.jsonl") if q["split"] == "test"}
    for name in NAMES:
        response_ids = [r["question_id"] for r in rows(FROZEN / f"test_{name}.jsonl")]
        if len(response_ids) != 90 or set(response_ids) != expected_ids:
            raise ValueError("Incomplete or duplicate test responses: " + name)
    return {"integrity": "passed", "files_checked": len(manifest["files"]),
            "dataset_content_digest": digest, "test_questions": 90,
            "configuration_outputs": 270, "dataset_validation": checked,
            "answer_human_review": "not completed; source review is a different task"}


def offline_grader(work):
    """Execute selected original functions; never import services package __init__."""
    gate = load_file("frozen_evidence_gate", REPO / "apps/api/services/chat/evidence_gate.py")
    path = REPO / "apps/api/scripts/grade_application.py"
    wanted = {"read", "average", "ratio", "disputed_confusion", "bootstrap", "score", "aggregate_judgments"}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in definitions} != wanted:
        raise ValueError("Original scorer function inventory changed")
    namespace = {"json": json, "random": random, "statistics": statistics,
                 "Path": Path, "NAMES": NAMES, "normalize_value": gate.normalize_value,
                 "eligible_sources": gate.eligible_sources,
                 "app": SimpleNamespace(DATA=DATA, WORK=work, write_json=write)}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def correct_costs(work):
    """Idempotently derive C costs from immutable B/C traces, including failures."""
    candidates = {r["question_id"]: r for r in rows(work / "test_B_graph.jsonl")}
    records = rows(work / "test_C_verified.jsonl")
    scored = read(work / "test_C_verified_scores.json")
    by_id = {r["question_id"]: r for r in scored}
    for record in records:
        candidate = candidates[record["question_id"]]
        usage = record["llm_usage"] + candidate["llm_usage"]
        target = by_id[record["question_id"]]
        target["prompt_tokens"] = sum(item.get("usage", {}).get("prompt_tokens", 0) for item in usage)
        target["completion_tokens"] = sum(item.get("usage", {}).get("completion_tokens", 0) for item in usage)
        target["wall_seconds"] = record["wall_seconds"] - (record["retrieval_wall_seconds"] if record.get("error") else 0)
    summary = read(work / "test_results.json")
    c = summary["C_verified"]
    times = sorted(r["wall_seconds"] for r in scored)
    c.update(median_wall_seconds=statistics.median(times),
             p95_wall_seconds=times[max(0, int(.95 * len(times) + .999) - 1)],
             mean_wall_seconds=statistics.mean(times),
             mean_prompt_tokens=statistics.mean(r["prompt_tokens"] for r in scored),
             mean_completion_tokens=statistics.mean(r["completion_tokens"] for r in scored))
    write(work / "test_C_verified_scores.json", scored)
    write(work / "test_results.json", summary)


def analyze(work):
    """Post-hoc diagnostics; preserve the original primary outcome and denominator."""
    gate = load_file("analysis_gate", REPO / "apps/api/services/chat/evidence_gate.py")
    questions = {q["question_id"]: q for q in rows(DATA / "private/questions.jsonl") if q["split"] == "test"}
    outputs = {name: {r["question_id"]: r for r in rows(work / f"test_{name}.jsonl")} for name in NAMES}
    scores = {name: {r["question_id"]: r for r in read(work / f"test_{name}_scores.json")} for name in NAMES}
    subsets = {}
    for label, predicate in (("all_test", lambda q: True),
                             ("excluding_insufficient", lambda q: q["expected_status"] != "insufficient"),
                             ("normally_answerable", lambda q: q["expected_status"] == "answerable")):
        ids = [qid for qid, q in questions.items() if predicate(q)]
        subsets[label] = {name: {"correct": sum(scores[name][qid]["structured_correct"] for qid in ids),
                                "n": len(ids), "accuracy": statistics.mean(scores[name][qid]["structured_correct"] for qid in ids)} for name in NAMES}
    failures = []
    for qid, record in outputs["C_verified"].items():
        if not record.get("error"):
            continue
        allowed, excluded = gate.eligible_sources(questions[qid]["question"], record["sources"])
        eligible = [record["sources"][i - 1] for i in sorted(allowed)]
        proposal = json.loads(record["verifier_raw_response"])
        quote_checks = [{"source": item.get("source"),
                         "source_exists": isinstance(item.get("source"), int) and 1 <= item["source"] <= len(eligible),
                         "exact_quote_present": isinstance(item.get("source"), int) and 1 <= item["source"] <= len(eligible)
                         and item.get("quote", "") in eligible[item["source"] - 1]["visible_text"]}
                        for item in proposal.get("evidence", [])]
        failures.append({"question_id": qid, "category": questions[qid]["category"],
                         "first_validation_failure": record["error"].split(": ", 1)[-1],
                         "missing_values": not bool(proposal.get("values")),
                         "missing_evidence": not bool(proposal.get("evidence")),
                         "proposal_status": proposal.get("status"), "proposal_values": proposal.get("values"),
                         "proposal_matches_gold_status_and_values": proposal.get("status") == questions[qid]["expected_status"]
                         and set(map(gate.normalize_value, proposal.get("values", []))) == set(map(gate.normalize_value, questions[qid]["required_values"])),
                         "eligible_source_count": len(eligible), "excluded_sources": excluded,
                         "quote_diagnostics": quote_checks,
                         "interpretation": "Post-hoc mechanical audit; not an independent semantic grade. Multiple defects may coexist."})
    draft = []
    for qid, q in questions.items():
        if q["category"] != "draft_conflict":
            continue
        record = outputs["C_verified"][qid]
        visible = " ".join(s["visible_text"] for s in record["sources"])
        draft.append({"question_id": qid, "A_correct": scores["A_vector"][qid]["structured_correct"],
                      "B_correct": scores["B_graph"][qid]["structured_correct"],
                      "C_correct": scores["C_verified"][qid]["structured_correct"],
                      "C_failure": record.get("error"),
                      "governance_sentence_visible": "draft proposals do not replace an approved register" in visible.lower(),
                      "retrieval_evidence_coverage": scores["C_verified"][qid]["retrieval_evidence_coverage"],
                      "decision_method": record.get("prediction", {}).get("decision_method")})
    summary = read(work / "test_results.json")
    uncertainty = {name: {status: {"n": len(selected), "status_correct": sum(r["status_correct"] for r in selected)}
                          for status in ("disputed", "insufficient")
                          if (selected := [r for r in scores[name].values() if r["expected_status"] == status])}
                   for name in NAMES}
    return {"analysis_status": "post-hoc; no new inference or outcome replacement",
            "subsets": subsets, "paired_C_vs_A": summary["C_verified"]["delta_vs_A_vector"],
            "paired_C_vs_B": summary["C_verified"]["delta_vs_B_graph"],
            "uncertainty_status_breakdown": uncertainty,
            "failures_by_first_mechanism": dict(Counter(r["first_validation_failure"] for r in failures)),
            "failures_by_category": dict(Counter(r["category"] for r in failures)),
            "failed_proposals_matching_gold_status_and_values": sum(r["proposal_matches_gold_status_and_values"] for r in failures),
            "failed_proposals_with_missing_values": sum(r["missing_values"] for r in failures),
            "failed_proposals_with_missing_evidence": sum(r["missing_evidence"] for r in failures),
            "failed_proposals_with_invalid_or_nonexact_quotes": sum(any(not c["exact_quote_present"] for c in r["quote_diagnostics"]) for r in failures),
            "failure_cases": failures, "draft_cases": draft,
            "draft_summary": {"questions": len(draft), "C_execution_failures": sum(bool(r["C_failure"]) for r in draft),
                              "governance_visible_questions": sum(r["governance_sentence_visible"] for r in draft),
                              "A_correct_C_wrong": [r["question_id"] for r in draft if r["A_correct"] and not r["C_correct"]],
                              "A_wrong_C_correct": [r["question_id"] for r in draft if not r["A_correct"] and r["C_correct"]]},
            "claim_boundary": "Controlled template-aligned verification; no established general QA superiority, independent human answer validation, or graph repair."}


def replay(destination, source=FROZEN):
    audit()
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Use a NEW output directory; frozen or previous outputs will not be overwritten")
    destination.mkdir(parents=True)
    for name in NAMES:
        shutil.copyfile(source / f"test_{name}.jsonl", destination / f"test_{name}.jsonl")
    if (source / "test_ai_grading.jsonl").exists():
        shutil.copyfile(source / "test_ai_grading.jsonl", destination / "test_ai_grading.jsonl")
    grader = offline_grader(destination)
    # The frozen scorer prints pre-erratum costs. Expose only corrected totals.
    with redirect_stdout(io.StringIO()):
        grader["score"]("test")
    correct_costs(destination)
    if (destination / "test_ai_grading.jsonl").exists():
        grader["aggregate_judgments"]("test")
    analysis = analyze(destination)
    write(destination / "posthoc_analysis.json", analysis)
    if source.resolve() == FROZEN.resolve():
        if read(destination / "test_results.json") != read(FROZEN / "test_results.json"):
            raise ValueError("Offline replay differs from the retained corrected summary")
        for name in NAMES:
            if read(destination / f"test_{name}_scores.json") != read(FROZEN / f"test_{name}_scores.json"):
                raise ValueError("Per-question replay mismatch: " + name)
        if read(destination / "test_ai_grading_summary.json") != read(FROZEN / "test_ai_grading_summary.json"):
            raise ValueError("AI grading aggregation differs")
    write(destination / "replay_receipt.json", {"offline": True, "models_called": False,
          "source": "published frozen traces" if source.resolve() == FROZEN.resolve() else "user-selected new run",
          "original_files_modified": False, "original_summary_matched": source.resolve() == FROZEN.resolve()})
    return {"destination": str(destination), "replay": "passed", "subsets": analysis["subsets"],
            "paired_C_vs_A": analysis["paired_C_vs_A"], "draft_summary": analysis["draft_summary"]}


def prepare_inference():
    """Stage the original runner's paths in a clean checkout; do not run a model."""
    audit()
    manifest = read(HERE / "publication_manifest.json")
    for name in RUNTIME_SNAPSHOT_FILES:
        expected = manifest["files"][name]
        path = REPO / name
        if not path.is_file() or sha(path, expected["newline_canonicalized"]) != expected["published_sha256"]:
            raise ValueError(
                "Fresh inference requires the frozen runtime: restore " + name
                + " from experiments/controlled_qa/runtime_snapshot in a separate clean checkout."
            )
    target = REPO / "output/research_benchmark"
    if target.exists():
        raise ValueError("Inference staging requires a clean checkout without output/research_benchmark. Existing research files are protected.")
    shutil.copytree(DATA, target / "akgb_synthetic_v1")
    freeze = read(FROZEN / "experiment_freeze.json")
    freeze["publication_lineage"] = {"original_frozen_utc": freeze["frozen_utc"],
        "original_publication_file": "experiments/controlled_qa/frozen/experiment_freeze.json",
        "change": "Resolve platform path separators and working-tree line endings only; no policy or source change.",
        "interpretation": "Reproduction after test disclosure, not a new untouched held-out evaluation."}
    freeze["code_sha256"] = {str(relative_path(name)): sha(REPO / relative_path(name)) for name in freeze["code_sha256"]}
    app = target / "application"
    freeze["settings"] = {"database": "sqlite+aiosqlite:///" + (app / "evaluation.sqlite").as_posix(),
                          "chroma_path": str(app / "chroma"), "llm_endpoint": "http://127.0.0.1:11434/v1"}
    write(app / "experiment_freeze.json", freeze)
    return {"prepared": str(target), "services_started": False,
            "next": "Follow README for dependency/model setup and the original headless ingestion/run commands."}


def rebuild_benchmark(destination):
    """Rebuild facts/sources from the generator plan and retained neutral prose."""
    audit()
    if destination.exists():
        raise ValueError("Benchmark rebuild requires a new output directory")
    generator = load_file("rebuild_generator", REPO / "apps/api/scripts/research_benchmark.py")
    shutil.copytree(DATA / "private/prose_cache", destination / "private/prose_cache")
    # A missing cached family must fail rather than silently calling a model.
    def no_generation(*args, **kwargs):
        raise RuntimeError("Offline rebuild cannot contact Ollama; required prose cache is missing")
    generator.ollama = no_generation
    args = SimpleNamespace(output=str(destination), seed=26014, families_per_category=4,
                           limit_families=0, mode="ollama", model="qwen2.5:1.5b",
                           base_url="http://127.0.0.1:11434")
    with redirect_stdout(io.StringIO()):
        generator.generate(args)
    original = read(FROZEN / "experiment_freeze.json")["dataset_content_digest"]
    if generator.dataset_content_digest(destination) != original:
        raise ValueError("Rebuilt source/gold content differs from the frozen dataset")
    return {"rebuild": "matched frozen dataset content", "sources": 96,
            "models_called": False, "review_status": "pending in the new workspace; no acceptance invented"}


def human_packet(destination):
    audit()
    if destination.exists():
        raise ValueError("Use a new human-review directory")
    packet = destination / "reviewer_packet"
    corpus = packet / "sources"
    shutil.copytree(DATA / "raw/test", corpus)
    questions = [q for q in rows(DATA / "private/questions.jsonl") if q["split"] == "test"]
    docs = rows(DATA / "private/documents.jsonl")
    outputs = {name: {r["question_id"]: r for r in rows(FROZEN / f"test_{name}.jsonl")} for name in NAMES}
    selected = []
    # Exactly five/category; every held-out family contributes at least one item.
    for category in sorted({q["category"] for q in questions}):
        families = sorted({q["family_id"] for q in questions if q["category"] == category})
        for index, family in enumerate(families):
            candidates = sorted((q for q in questions if q["family_id"] == family), key=lambda q: q["question_id"])
            random.Random("AKGB-human-audit-26014-" + family).shuffle(candidates)
            selected.extend(candidates[:2 if index < 2 else 1])
    random.Random(26014).shuffle(selected)
    key = []
    records = []
    sections = []
    for number, q in enumerate(selected, 1):
        item_id = f"H{number:02d}"
        names = list(NAMES)
        random.Random("human-answer-order-26014-" + q["question_id"]).shuffle(names)
        parts = [f'<section id="{item_id}"><h2>{item_id}: {html.escape(q["question"])}</h2>']
        parts.append("<h3>Complete source documents for this scenario</h3>")
        for d in docs:
            if d["family_id"] == q["family_id"]:
                parts.append(f'<details><summary>{d["doc_id"]}</summary><pre>{html.escape((DATA / d["path"]).read_text(encoding="utf-8"))}</pre></details>')
        parts.append("<h3>Numbered excerpts actually available to these answers</h3>")
        for i, source in enumerate(outputs[NAMES[0]][q["question_id"]]["sources"], 1):
            parts.append(f'<details><summary>[{i}] {html.escape(source["filename"])}</summary><pre>{html.escape(source["visible_text"])}</pre></details>')
        for label, name in zip(("R1", "R2", "R3"), names):
            record = outputs[name][q["question_id"]]
            answer = record.get("prediction", {}).get("answer", "") if not record.get("error") else "[Execution failed; no final answer was delivered.]"
            parts.append(f'<h3>{label}</h3><p>{html.escape(answer)}</p>')
            key.append({"item_id": item_id, "question_id": q["question_id"], "category": q["category"], "answer_label": label, "configuration": name})
            records.append({"item_id": item_id, "answer_label": label, "reviewer_id": "", "correctness": "",
                            "missing_information": "", "unsupported_statements": "", "citation_support": "", "rationale": ""})
        sections.append("".join(parts) + "</section>")
    instructions = '''<h1>Post-hoc human answer audit</h1><p>30 questions; 90 anonymous answers. Five questions per category, covering all 18 held-out families. Selection and shuffling use fixed rules independent of system success. This is model-label blinding, not a prospective blind experiment.</p>
<p>Read the question, complete scenario documents, and numbered retrieved excerpts. For absent-information claims you may search every file in the adjacent sources/ folder (all 72 test sources). Sources may contain deliberately wrong statements. Apply validity dates, scope, approval rules, and unresolved disagreements; do not use publication date alone or count copies as votes.</p>
<p>Fill grades.csv. correctness: correct / partial / incorrect. missing_information: none / minor / major. unsupported_statements: none / minor / major. citation_support: all / some / none / not_applicable. Use not_applicable for a claim-free refusal or failed execution; record a failed execution as incorrect. A wrong or inapplicable source cannot support the requested answer merely because a quotation exists. For disputed answers require all supported alternatives and explicit uncertainty. Explain material defects and identify documents in rationale. Record your own reviewer ID.</p>
<p>Grade answers yourself before consulting the manuscript, public experiment logs, AI grades, organizer key, or another reviewer. Answer length/style may reveal a configuration, so blinding is imperfect. A second reviewer should complete a separate copy before discussing disagreements. No result in this packet has been human-graded yet.</p>'''
    (packet / "review.html").write_text('<!doctype html><meta charset="utf-8"><title>AKGB human audit</title><style>body{font:16px Georgia;max-width:1000px;margin:40px auto;padding:20px;line-height:1.5}pre{white-space:pre-wrap;font:14px Consolas}section{border-top:2px solid #555;margin-top:36px}details{padding:6px}p{white-space:pre-wrap}</style>' + instructions + "".join(sections), encoding="utf-8")
    with (packet / "grades.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    write(destination / "organizer_only/answer_key.json", key)
    write(destination / "organizer_only/selection_receipt.json", {"type": "post-hoc stratified human audit",
          "seed": 26014, "questions": 30, "answers": 90, "families": len({q["family_id"] for q in selected}),
          "by_category": dict(Counter(q["category"] for q in selected)), "human_grades_received": False,
          "rule": "Sorted categories and families; fixed family-seeded shuffle; take 2,2,1 items across each category's three families; then shuffle questions and answers with fixed seeds."})
    archive = destination / "Reviewer_Packet.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(packet.rglob("*")):
            if path.is_file(): zipped.write(path, path.relative_to(packet))
    return {"reviewer_zip": str(archive), "questions": 30, "answers": 90,
            "human_assessment": "pending; send only Reviewer_Packet.zip to the reviewer"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "replay", "prepare-inference", "human-packet", "rebuild-benchmark"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input-root", type=Path, default=FROZEN)
    args = parser.parse_args()
    if args.action == "audit": result = audit()
    elif args.action == "prepare-inference": result = prepare_inference()
    elif args.output is None: parser.error("--output is required and must name a new directory")
    elif args.action == "human-packet": result = human_packet(args.output)
    elif args.action == "rebuild-benchmark": result = rebuild_benchmark(args.output)
    else: result = replay(args.output, args.input_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
