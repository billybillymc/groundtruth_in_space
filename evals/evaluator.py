#!/usr/bin/env python3
"""
Adamant RAG Evaluator
=====================
Evaluation of the Adamant codebase intelligence agent using deterministic keyword
checks, rubric scoring, and LLM-as-judge semantic evaluation.
Calls the RAG pipeline directly (no HTTP). Loads YAML eval suites and scores
responses using keyword matching, rubric checks, source validation, latency,
and LLM-based coherence/correctness/groundedness judgments.

Usage:
    python -m evals.evaluator [OPTIONS]

Options:
    --suite         Filter to a specific suite name (substring match)
    --output-file   Path to write JSON results (default: evals/results/TIMESTAMP.json)
    --timeout       Max seconds per query (default: 60)
    --skip-llm-judge  Skip the LLM-as-judge evaluator (faster, cheaper)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("evaluator")

# ── Paths ─────────────────────────────────────────────────────────────────────

EVALS_DIR = Path(__file__).parent
SUITES_DIR = EVALS_DIR / "suites"
RESULTS_DIR = EVALS_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── YAML loader ──────────────────────────────────────────────────────────────


def load_yaml_suites(directory: Path) -> list[dict]:
    """Load all YAML eval files from a directory."""
    suites = []
    for path in sorted(directory.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        if not data.get("examples"):
            log.info("Skipping %s (no examples)", path.name)
            continue
        data["_source_file"] = str(path)
        suites.append(data)
        log.info("Loaded %d examples from %s", len(data["examples"]), path.name)
    return suites


# ── Query runner ─────────────────────────────────────────────────────────────


def run_query(message: str, timeout: float = 60.0) -> dict:
    """Run a query through the RAG pipeline and return a normalized output dict."""
    from src.synthesis.chain import query

    start = time.monotonic()
    try:
        result = query(message)
        return {
            "message": result.answer,
            "sources": [
                {
                    "file_path": s.chunk.file_path,
                    "score": s.score,
                    "chunk_type": s.chunk.chunk_type,
                }
                for s in result.sources
            ],
            "latency_ms": result.latency_ms,
            "error": None,
        }
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return {
            "message": "",
            "sources": [],
            "latency_ms": elapsed,
            "error": str(exc),
        }


# ── Evaluators ───────────────────────────────────────────────────────────────


def _response_text(output: dict) -> str:
    return (output.get("message") or "").lower()


def eval_keyword_contains(output: dict, reference: dict) -> dict:
    """All items in reference_outputs.contains must appear in the response."""
    required: list[str] = reference.get("contains", [])
    if not required:
        return {"key": "keyword_contains", "score": 1.0, "comment": "no required terms"}
    text = _response_text(output)
    missing = [kw for kw in required if kw.lower() not in text]
    score = 1.0 - len(missing) / len(required)
    comment = f"missing: {missing}" if missing else "all required terms present"
    return {"key": "keyword_contains", "score": round(score, 3), "comment": comment}


def eval_keyword_contains_any(output: dict, reference: dict) -> dict:
    """At least one item in reference_outputs.contains_any must appear."""
    candidates: list[str] = reference.get("contains_any", [])
    if not candidates:
        return {"key": "keyword_contains_any", "score": 1.0, "comment": "no candidates"}
    text = _response_text(output)
    found = [kw for kw in candidates if kw.lower() in text]
    score = 1.0 if found else 0.0
    comment = f"matched: {found}" if found else f"none of {candidates} found"
    return {"key": "keyword_contains_any", "score": score, "comment": comment}


def eval_does_not_contain(output: dict, reference: dict) -> dict:
    """Items in reference_outputs.does_not_contain must NOT appear."""
    forbidden: list[str] = reference.get("does_not_contain", [])
    if not forbidden:
        return {"key": "does_not_contain", "score": 1.0, "comment": "no forbidden terms"}
    text = _response_text(output)
    violations = [kw for kw in forbidden if kw.lower() in text]
    score = 1.0 - len(violations) / len(forbidden)
    comment = f"violations: {violations}" if violations else "no forbidden terms present"
    return {"key": "does_not_contain", "score": round(score, 3), "comment": comment}


def eval_rubric(output: dict, reference: dict) -> dict:
    """Keyword-based rubric scoring. Each criterion has keywords and a weight."""
    rubric: list[dict] = reference.get("rubric", [])
    if not rubric:
        return {"key": "rubric", "score": 1.0, "comment": "no rubric defined"}
    text = _response_text(output)
    total_weight = sum(r.get("weight", 1.0) for r in rubric)
    weighted_score = 0.0
    details = []
    for criterion in rubric:
        weight = criterion.get("weight", 1.0)
        keywords: list[str] = criterion.get("keywords", [])
        key = criterion.get("key", "unknown")
        if keywords:
            matched = any(kw.lower() in text for kw in keywords)
        else:
            # Fall back to extracting long words from criterion text
            stop_words = {"that", "with", "from", "this", "does", "into", "more", "than", "have", "been"}
            words = [
                w.lower().strip(",.()") for w in criterion.get("criterion", "").split()
                if len(w) > 4 and w.lower() not in stop_words
            ]
            matched = any(w in text for w in words) if words else True
        criterion_score = 1.0 if matched else 0.0
        weighted_score += criterion_score * weight
        details.append(f"{key}={'pass' if matched else 'FAIL'}(w={weight})")
    final_score = weighted_score / total_weight if total_weight else 0.0
    return {"key": "rubric", "score": round(final_score, 3), "comment": " | ".join(details)}


def eval_no_error(output: dict, _reference: dict) -> dict:
    """Penalize responses that look like system errors."""
    text = _response_text(output)
    error_signals = ["traceback", "error 500", "internal server error", "exception"]
    violations = [s for s in error_signals if s in text]
    if output.get("error"):
        violations.append(f"runtime: {output['error'][:80]}")
    score = 0.0 if violations else 1.0
    return {"key": "no_error", "score": score, "comment": f"errors: {violations}" if violations else "clean"}


def eval_latency(output: dict, reference: dict) -> dict:
    """Check response latency against max_latency_s."""
    max_latency = reference.get("max_latency_s")
    if not max_latency:
        return {"key": "latency", "score": 1.0, "comment": "no latency requirement"}
    latency_ms = output.get("latency_ms", 0)
    actual_s = latency_ms / 1000.0
    if actual_s <= max_latency:
        return {"key": "latency", "score": 1.0, "comment": f"{actual_s:.1f}s <= {max_latency}s"}
    score = max(0.0, 1.0 - (actual_s - max_latency) / max_latency)
    return {"key": "latency", "score": round(score, 3), "comment": f"{actual_s:.1f}s > {max_latency}s limit"}


def eval_has_sources(output: dict, _reference: dict) -> dict:
    """Check that sources were returned."""
    sources = output.get("sources", [])
    score = 1.0 if sources else 0.0
    return {"key": "has_sources", "score": score, "comment": f"{len(sources)} sources" if sources else "no sources"}


def eval_not_refusal(output: dict, _reference: dict) -> dict:
    """Penalize if the model refused to answer."""
    text = _response_text(output)
    refusal_phrases = ["cannot find the answer", "i cannot find", "not contain enough information"]
    refused = any(p in text for p in refusal_phrases)
    return {"key": "not_refusal", "score": 0.0 if refused else 1.0, "comment": "refused" if refused else "answered"}


def eval_expects_refusal(output: dict, reference: dict) -> dict:
    """For negative cases: the model SHOULD refuse or caveat, not hallucinate."""
    if not reference.get("expects_refusal"):
        return {"key": "expects_refusal", "score": 1.0, "comment": "not a refusal test"}
    text = _response_text(output)
    hedging = [
        "i don't have", "i do not have", "cannot find", "no information",
        "not found in", "not present in", "not available", "i'm not sure",
        "i am not sure", "no relevant", "unable to find", "doesn't appear",
        "does not appear", "not in the codebase", "not part of",
    ]
    hedged = any(p in text for p in hedging)
    score = 1.0 if hedged else 0.0
    comment = "correctly hedged/refused" if hedged else "answered confidently (expected refusal)"
    return {"key": "expects_refusal", "score": score, "comment": comment}


# ── LLM-as-Judge ────────────────────────────────────────────────────────────

_judge_llm = None
_SKIP_LLM_JUDGE = False

LLM_JUDGE_PROMPT = """\
You are an expert evaluator for a code intelligence system that answers questions about the Adamant Ada codebase.

Given a QUESTION, the system's ANSWER, and the list of SOURCE FILES retrieved, score the answer on three dimensions. Each dimension is scored 1-5.

## Dimensions

1. **Coherence** (1-5): Is the answer well-structured, clear, and easy to follow? Does it flow logically?
2. **Correctness** (1-5): Based on the source files cited and your understanding of software systems, does the answer appear technically accurate? Are Ada constructs described correctly?
3. **Groundedness** (1-5): Does the answer stick to information from the retrieved sources, or does it introduce claims not supported by the context? (5 = fully grounded, 1 = mostly fabricated)

## Input

QUESTION: {question}

ANSWER: {answer}

SOURCE FILES: {sources}

## Output

Respond with ONLY a JSON object (no markdown fences):
{{"coherence": <int>, "correctness": <int>, "groundedness": <int>, "reasoning": "<brief explanation>"}}
"""


def _get_judge_llm():
    global _judge_llm
    if _judge_llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from src.config import GOOGLE_API_KEY
        _judge_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.0,
        )
    return _judge_llm


def eval_llm_judge(output: dict, reference: dict) -> dict:
    """Use an LLM to score coherence, correctness, and groundedness."""
    if _SKIP_LLM_JUDGE:
        return {"key": "llm_judge", "score": 1.0, "comment": "skipped"}

    text = output.get("message", "")
    if not text or output.get("error"):
        return {"key": "llm_judge", "score": 0.0, "comment": "no answer to judge"}

    # For negative/refusal cases, skip LLM judge (handled by expects_refusal)
    if reference.get("expects_refusal"):
        return {"key": "llm_judge", "score": 1.0, "comment": "skipped for refusal test"}

    sources = ", ".join(s["file_path"] for s in output.get("sources", []))
    question = reference.get("_question", "unknown")

    try:
        llm = _get_judge_llm()
        prompt = LLM_JUDGE_PROMPT.format(
            question=question,
            answer=text[:2000],
            sources=sources or "none",
        )
        response = llm.invoke(prompt)
        content = response.content.strip()
        # Strip markdown fences if present
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        scores = json.loads(content)

        coherence = int(scores.get("coherence", 3))
        correctness = int(scores.get("correctness", 3))
        groundedness = int(scores.get("groundedness", 3))
        reasoning = scores.get("reasoning", "")

        # Normalize 1-5 scale to 0-1
        avg = (coherence + correctness + groundedness) / 3.0
        normalized = (avg - 1.0) / 4.0  # maps 1->0, 5->1

        comment = (
            f"coherence={coherence}/5 correctness={correctness}/5 "
            f"groundedness={groundedness}/5 | {reasoning[:120]}"
        )
        return {"key": "llm_judge", "score": round(normalized, 3), "comment": comment}

    except Exception as exc:
        log.warning("LLM judge failed: %s", exc)
        return {"key": "llm_judge", "score": 0.5, "comment": f"judge error: {str(exc)[:80]}"}


ALL_EVALUATORS = [
    eval_keyword_contains,
    eval_keyword_contains_any,
    eval_does_not_contain,
    eval_rubric,
    eval_no_error,
    eval_latency,
    eval_has_sources,
    eval_not_refusal,
    eval_expects_refusal,
    eval_llm_judge,
]


# ── Scoring ──────────────────────────────────────────────────────────────────


def score_example(output: dict, reference: dict) -> dict[str, dict]:
    """Run all evaluators and return {evaluator_key: result}."""
    results = {}
    for fn in ALL_EVALUATORS:
        try:
            result = fn(output, reference)
            results[result["key"]] = result
        except Exception as exc:
            key = fn.__name__.replace("eval_", "")
            results[key] = {"key": key, "score": 0.0, "comment": f"evaluator error: {exc}"}
    return results


def aggregate_score(scores: dict[str, dict]) -> float:
    """Average of all scores that had actual checks."""
    values = [
        v["score"] for v in scores.values()
        if "no " not in v.get("comment", "") and "no_" not in v.get("comment", "")
    ]
    return round(sum(values) / len(values), 3) if values else 1.0


# ── Runner ───────────────────────────────────────────────────────────────────


def run_example(ex: dict, suite_name: str, timeout: float) -> dict:
    """Run a single example and return the result record."""
    ex_id = ex["id"]
    description = ex.get("description", "")
    inputs = ex.get("inputs", {})
    reference = ex.get("reference_outputs", {})
    metadata = ex.get("metadata", {})

    log.info("  [%s] %s", ex_id, description[:70])

    output = run_query(inputs["message"], timeout)

    # Inject the question into reference so LLM judge can see it
    reference["_question"] = inputs["message"]

    if output.get("error"):
        scores = {
            "no_error": {"key": "no_error", "score": 0.0, "comment": f"error: {output['error'][:100]}"},
            "not_refusal": {"key": "not_refusal", "score": 0.0, "comment": "error"},
        }
    else:
        scores = score_example(output, reference)

    agg = aggregate_score(scores)
    passed = agg >= 0.7

    record = {
        "eval_id": ex_id,
        "dataset": suite_name,
        "description": description,
        "elapsed_s": round(output.get("latency_ms", 0) / 1000, 2),
        "passed": passed,
        "aggregate_score": agg,
        "scores": scores,
        "input": inputs["message"],
        "output_message": (output.get("message") or "")[:500],
        "output_sources": [s["file_path"] for s in output.get("sources", [])],
        "error": output.get("error"),
        "metadata": metadata,
    }

    status = "PASS" if passed else "FAIL"
    log.info("    %s (score=%.2f, %.1fs)", status, agg, record["elapsed_s"])
    return record


def run_suite(suite: dict, timeout: float) -> list[dict]:
    """Run all examples in a suite sequentially."""
    dataset_name = suite["dataset_name"]
    examples = suite.get("examples", [])
    log.info("=== Running suite: %s (%d examples) ===", dataset_name, len(examples))
    results = []
    for ex in examples:
        results.append(run_example(ex, dataset_name, timeout))
        time.sleep(1)  # rate limit buffer for Cohere/Pinecone
    return results


# ── Summary & reporting ──────────────────────────────────────────────────────


def print_summary(all_results: list[dict]) -> None:
    total = len(all_results)
    if not total:
        log.info("No results to summarize.")
        return
    passed = sum(1 for r in all_results if r["passed"])
    failed = total - passed
    avg_score = round(sum(r["aggregate_score"] for r in all_results) / total, 3)

    print("\n" + "=" * 60)
    print(f"  EVAL SUMMARY  -  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print(f"  Total examples : {total}")
    print(f"  Passed (>=0.7) : {passed}  ({100 * passed // total}%)")
    print(f"  Failed         : {failed}")
    print(f"  Avg score      : {avg_score}")
    print()

    by_dataset: dict[str, list[dict]] = {}
    for r in all_results:
        by_dataset.setdefault(r["dataset"], []).append(r)

    for ds_name, ds_results in by_dataset.items():
        ds_pass = sum(1 for r in ds_results if r["passed"])
        ds_avg = round(sum(r["aggregate_score"] for r in ds_results) / len(ds_results), 3)
        print(f"  [{ds_name}]")
        print(f"    Pass: {ds_pass}/{len(ds_results)}  Avg: {ds_avg}")
        for r in ds_results:
            icon = "PASS" if r["passed"] else "FAIL"
            print(f"    [{icon}] {r['eval_id']:20s} score={r['aggregate_score']:.2f}  {r.get('error') or ''}")
        print()

    p0_failures = [r for r in all_results if not r["passed"] and r.get("metadata", {}).get("priority") == "p0"]
    if p0_failures:
        print(f"  [!] P0 FAILURES ({len(p0_failures)}):")
        for r in p0_failures:
            print(f"     {r['eval_id']}: {r['description'][:60]}")
        print()

    print("=" * 60)


def save_results(all_results: list[dict], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(all_results),
        "passed": sum(1 for r in all_results if r["passed"]),
        "avg_score": round(sum(r["aggregate_score"] for r in all_results) / len(all_results), 3) if all_results else 0.0,
        "results": all_results,
    }
    with open(output_file, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    log.info("Results saved to %s", output_file)


def save_overview_md(all_results: list[dict], output_file: Path) -> None:
    if not all_results:
        return
    overview_file = output_file.with_suffix(".md")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    avg_score = round(sum(r["aggregate_score"] for r in all_results) / total, 3)

    lines = [
        f"# Adamant Eval Results - {timestamp}",
        "",
        "## Summary",
        f"- **Passed:** {passed}/{total} ({100 * passed // total}%)",
        f"- **Failed:** {total - passed}",
        f"- **Avg Score:** {avg_score}",
        "",
        "---",
        "",
        "## Suites",
        "",
    ]

    by_dataset: dict[str, list[dict]] = {}
    for r in all_results:
        by_dataset.setdefault(r["dataset"], []).append(r)

    for ds_name, ds_results in sorted(by_dataset.items()):
        ds_pass = sum(1 for r in ds_results if r["passed"])
        ds_total = len(ds_results)
        lines.append(f"### {ds_name}: {ds_pass}/{ds_total}")
        for r in ds_results:
            status = "PASS" if r["passed"] else "FAIL"
            lines.append(f"- `{r['eval_id']}`: {status} ({r['aggregate_score']:.2f}) - {r['description'][:60]}")
        lines.append("")

    overview_file.write_text("\n".join(lines), encoding="utf-8")
    log.info("Overview saved to %s", overview_file)


# ── Main ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adamant RAG Evaluator")
    parser.add_argument("--suite", default=None, help="Filter to suite name (substring match)")
    parser.add_argument("--output-file", default=None, help="Path to write JSON results")
    parser.add_argument("--timeout", type=float, default=60.0, help="Max seconds per query")
    parser.add_argument("--skip-llm-judge", action="store_true", help="Skip LLM-as-judge (faster, cheaper)")
    return parser.parse_args()


def main() -> int:
    global _SKIP_LLM_JUDGE
    args = parse_args()
    _SKIP_LLM_JUDGE = args.skip_llm_judge
    if _SKIP_LLM_JUDGE:
        log.info("LLM-as-judge evaluator disabled")

    # Load suites
    all_suites = load_yaml_suites(SUITES_DIR)
    if not all_suites:
        log.error("No YAML eval files found in %s", SUITES_DIR)
        return 1

    total_examples = sum(len(s.get("examples", [])) for s in all_suites)
    log.info("Loaded %d suites (%d total examples)", len(all_suites), total_examples)

    if args.suite:
        all_suites = [s for s in all_suites if args.suite.lower() in s["dataset_name"].lower()]
        log.info("Filtered to %d suite(s) matching '%s'", len(all_suites), args.suite)

    # Run
    all_results: list[dict] = []
    for suite in all_suites:
        all_results.extend(run_suite(suite, args.timeout))

    # Report
    print_summary(all_results)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(args.output_file) if args.output_file else RESULTS_DIR / f"eval_{timestamp}.json"
    save_results(all_results, output_file)
    save_overview_md(all_results, output_file)

    p0_failures = [r for r in all_results if not r["passed"] and r.get("metadata", {}).get("priority") == "p0"]
    if p0_failures:
        log.warning("%d P0 failure(s)", len(p0_failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
