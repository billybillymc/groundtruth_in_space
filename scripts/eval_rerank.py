"""Eval: compare retrieval quality with vs. without Cohere reranking.

Runs a fixed set of queries through the RAG pipeline in both modes,
then prints a side-by-side report of sources, scores, and answers
so you can judge whether disabling rerank degrades quality.

Usage:
    python scripts/eval_rerank.py
"""

import sys
import os
import time
import json
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.synthesis.chain import (
    _get_embeddings,
    _get_pinecone_index,
    _get_cached_embedding,
    _put_cached_embedding,
    _get_llm,
    _get_prompt,
    _get_cohere_client,
    _format_context,
    _pinecone_query_to_docs,
    _deduplicate_by_file,
    _rerank,
    MAX_CONTEXT_CHARS,
    TOP_K,
)
from langchain_core.output_parsers import StrOutputParser

# ── Eval queries covering different aspects of the Adamant codebase ──
EVAL_QUERIES = [
    "How does the CCSDS packetizer create telemetry packets?",
    "What is the Tick component and how does it work?",
    "How are commands dispatched to components in Adamant?",
    "Explain the memory manager component.",
    "How does the sequence engine execute sequences?",
    "What fault protection mechanisms exist in Adamant?",
    "How does the parameter store manage parameter values?",
    "Describe the event filtering system.",
]


def _run_single_query(question, use_rerank):
    """Run one query, return (sources_info, answer, latency_ms)."""
    index = _get_pinecone_index()
    prompt = _get_prompt()
    llm = _get_llm()
    chain = prompt | llm | StrOutputParser()

    t0 = time.perf_counter()

    # Embed (with cache) and query Pinecone directly
    vec = _get_cached_embedding(question)
    if vec is None:
        vec = _get_embeddings().embed_query(question)
        _put_cached_embedding(question, vec)
    results = index.query(vector=vec, top_k=TOP_K * 2, include_metadata=True)
    raw_results = _pinecone_query_to_docs(results)
    deduped = _deduplicate_by_file(raw_results, limit=TOP_K)

    if use_rerank:
        final = _rerank(question, deduped, top_n=5)
    else:
        # Without rerank: just take top 5 by vector similarity
        final = deduped[:5]

    docs = [doc for doc, _ in final]
    context = _format_context(docs)
    answer = chain.invoke({"context": context, "question": question})

    elapsed = (time.perf_counter() - t0) * 1000

    sources = []
    for doc, score in final:
        m = doc.metadata
        sources.append({
            "file": m.get("file_path", "?"),
            "lines": f"{m.get('start_line', '?')}-{m.get('end_line', '?')}",
            "type": m.get("chunk_type", "?"),
            "score": round(score, 4),
        })

    return sources, answer, elapsed


def _truncate(s, n=120):
    return s[:n] + "..." if len(s) > n else s


def main():
    # Warm up singletons
    print("Warming up singletons...")
    _get_embeddings()
    _get_pinecone_index()
    _get_llm()
    _get_prompt()
    _get_cohere_client()
    print()

    results = []

    for i, q in enumerate(EVAL_QUERIES, 1):
        print(f"[{i}/{len(EVAL_QUERIES)}] {q}")

        print("  Running WITH rerank...")
        src_rerank, ans_rerank, lat_rerank = _run_single_query(q, use_rerank=True)

        print("  Running WITHOUT rerank...")
        src_no_rerank, ans_no_rerank, lat_no_rerank = _run_single_query(q, use_rerank=False)

        results.append({
            "query": q,
            "with_rerank": {
                "sources": src_rerank,
                "answer": ans_rerank,
                "latency_ms": round(lat_rerank),
            },
            "without_rerank": {
                "sources": src_no_rerank,
                "answer": ans_no_rerank,
                "latency_ms": round(lat_no_rerank),
            },
        })
        print()

    # ── Print report ──
    print("=" * 80)
    print("RERANK EVAL REPORT")
    print("=" * 80)

    total_lat_with = 0
    total_lat_without = 0
    source_overlap_scores = []

    for r in results:
        q = r["query"]
        wr = r["with_rerank"]
        nr = r["without_rerank"]

        total_lat_with += wr["latency_ms"]
        total_lat_without += nr["latency_ms"]

        # Compute source overlap (how many of the same files appear in both)
        files_with = {s["file"] for s in wr["sources"]}
        files_without = {s["file"] for s in nr["sources"]}
        if files_with:
            overlap = len(files_with & files_without) / len(files_with)
        else:
            overlap = 1.0
        source_overlap_scores.append(overlap)

        print(f"\nQ: {q}")
        print(f"  Latency:  rerank={wr['latency_ms']}ms  |  no-rerank={nr['latency_ms']}ms  |  saved={wr['latency_ms'] - nr['latency_ms']}ms")
        print(f"  Source overlap: {overlap:.0%}")

        print(f"  Sources WITH rerank:")
        for s in wr["sources"]:
            print(f"    {s['score']:.4f}  {s['file']}:{s['lines']} ({s['type']})")

        print(f"  Sources WITHOUT rerank:")
        for s in nr["sources"]:
            print(f"    {s['score']:.4f}  {s['file']}:{s['lines']} ({s['type']})")

        print(f"  Answer WITH rerank:    {_truncate(ans_rerank)}")
        print(f"  Answer WITHOUT rerank: {_truncate(ans_no_rerank)}")

    # ── Summary ──
    n = len(results)
    avg_overlap = sum(source_overlap_scores) / n if n else 0
    avg_lat_with = total_lat_with / n if n else 0
    avg_lat_without = total_lat_without / n if n else 0

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Queries evaluated:        {n}")
    print(f"  Avg latency WITH rerank:  {avg_lat_with:.0f}ms")
    print(f"  Avg latency WITHOUT:      {avg_lat_without:.0f}ms")
    print(f"  Avg latency saved:        {avg_lat_with - avg_lat_without:.0f}ms")
    print(f"  Avg source file overlap:  {avg_overlap:.0%}")
    print()
    print("  Interpretation:")
    print("    - High overlap (>80%) = reranking barely changes which files are retrieved")
    print("    - Low overlap (<50%)  = reranking significantly reshuffles results")
    print("    - Compare answers qualitatively to decide if rerank is worth the latency")
    print()

    # Save raw results for later review
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eval_rerank_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Raw results saved to: {out_path}")


if __name__ == "__main__":
    main()
