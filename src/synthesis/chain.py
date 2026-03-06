"""LCEL chain: retriever | prompt | llm | parser."""

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Generator, List, Tuple

import cohere
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone

from src.config import (
    CODEBASES,
    COHERE_API_KEY,
    EMBEDDING_MODEL,
    GOOGLE_API_KEY,
    LLM_MODEL,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    TOP_K,
)
from src.models import Chunk, QueryResult, RetrievedChunk
from src.synthesis.prompts import RAG_PROMPT_TEMPLATE

# Module-level singletons
_vectorstore = None
_embeddings = None
_pinecone_indexes = None
_llm = None
_prompt = None
_cohere_client = None

# ── Embedding cache ──────────────────────────────────────────
_embedding_cache: dict = {}  # normalized_query -> vector
_CACHE_MAX_SIZE = 256
_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "embedding_cache.json",
)


def _load_embedding_cache():
    """Load persisted embedding cache from disk."""
    global _embedding_cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r") as f:
                _embedding_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _embedding_cache = {}


def _save_embedding_cache():
    """Persist embedding cache to disk."""
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(_embedding_cache, f)


def _normalize_query(q: str) -> str:
    """Normalize a query string for cache lookup."""
    return " ".join(q.lower().split())


def _get_cached_embedding(query: str) -> list | None:
    """Return cached embedding vector or None."""
    if not _embedding_cache:
        _load_embedding_cache()
    key = _normalize_query(query)
    return _embedding_cache.get(key)


def _put_cached_embedding(query: str, vector: list):
    """Store an embedding in the cache, evicting oldest if full."""
    key = _normalize_query(query)
    if len(_embedding_cache) >= _CACHE_MAX_SIZE:
        # Evict first (oldest) entry
        oldest = next(iter(_embedding_cache))
        del _embedding_cache[oldest]
    _embedding_cache[key] = vector
    _save_embedding_cache()


MAX_CONTEXT_CHARS = 12000


def _format_context(docs: List[Document]) -> str:
    """Format retrieved documents into a context string with citations."""
    formatted = []
    total_chars = 0
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        file_path = meta.get("file_path", "unknown")
        start = meta.get("start_line", "?")
        end = meta.get("end_line", "?")
        chunk_type = meta.get("chunk_type", "")
        component = meta.get("component_name", "")
        codebase = meta.get("codebase", "")

        # Truncate individual chunks to keep total context manageable
        content = doc.page_content
        if total_chars + len(content) > MAX_CONTEXT_CHARS and formatted:
            content = content[:max(500, MAX_CONTEXT_CHARS - total_chars)] + "\n[...truncated]"

        header = f"[Source {i}]"
        if codebase:
            header += f" ({codebase})"
        header += f" {file_path}:{start}-{end}"
        if component:
            header += f" ({chunk_type}, {component})"
        formatted.append(f"{header}\n```\n{content}\n```")
        total_chars += len(content)
    return "\n\n".join(formatted)


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)
    return _embeddings


def _get_pinecone_indexes() -> dict:
    """Return dict of {codebase_name: pinecone_index} for all codebases."""
    global _pinecone_indexes
    if _pinecone_indexes is None:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_indexes = {}
        for cb_name, cb_config in CODEBASES.items():
            _pinecone_indexes[cb_name] = pc.Index(cb_config["index"])
    return _pinecone_indexes


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.0,
            thinking_budget=0,
        )
    return _llm


def _get_prompt() -> ChatPromptTemplate:
    global _prompt
    if _prompt is None:
        _prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
    return _prompt


def _get_cohere_client():
    global _cohere_client
    if _cohere_client is None and COHERE_API_KEY:
        _cohere_client = cohere.ClientV2(api_key=COHERE_API_KEY)
    return _cohere_client


def _rerank(
    question: str, docs_with_scores: List[Tuple[Document, float]], top_n: int = 5
) -> List[Tuple[Document, float]]:
    """Rerank documents using Cohere. Falls back to original order if unavailable."""
    client = _get_cohere_client()
    if client is None:
        return docs_with_scores[:top_n]

    try:
        texts = [doc.page_content for doc, _ in docs_with_scores]
        response = client.rerank(
            model="rerank-v3.5",
            query=question,
            documents=texts,
            top_n=top_n,
        )
        reranked = []
        for result in response.results:
            doc, _ = docs_with_scores[result.index]
            reranked.append((doc, result.relevance_score))
        return reranked
    except Exception as e:
        print(f"  Reranking failed, using vector scores: {e}")
        return docs_with_scores[:top_n]


def _deduplicate_by_file(
    docs_with_scores: List[Tuple[Document, float]], limit: int = 5, min_per_codebase: int = 2
) -> List[Tuple[Document, float]]:
    """Keep top chunks per unique file, ensuring each codebase gets min representation."""
    # Group by codebase, dedup by file within each
    by_codebase: dict = {}
    for doc, score in docs_with_scores:
        cb = doc.metadata.get("codebase", "unknown")
        fp = doc.metadata.get("file_path", "")
        if cb not in by_codebase:
            by_codebase[cb] = {}
        if fp not in by_codebase[cb]:
            by_codebase[cb][fp] = (doc, score)

    # Guarantee min_per_codebase slots for each codebase
    result = []
    remaining = []
    for cb, files in by_codebase.items():
        sorted_files = sorted(files.values(), key=lambda x: x[1], reverse=True)
        result.extend(sorted_files[:min_per_codebase])
        remaining.extend(sorted_files[min_per_codebase:])

    # Fill remaining slots with best scores globally
    remaining.sort(key=lambda x: x[1], reverse=True)
    slots_left = limit - len(result)
    if slots_left > 0:
        result.extend(remaining[:slots_left])
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def _pinecone_query_to_docs(
    results: dict, codebase: str = "",
) -> List[Tuple[Document, float]]:
    """Convert raw Pinecone query results into (Document, score) pairs."""
    docs = []
    for match in results.get("matches", []):
        meta = match.get("metadata", {})
        text = meta.pop("text", "")
        if codebase and "codebase" not in meta:
            meta["codebase"] = codebase
        doc = Document(page_content=text, metadata=meta)
        docs.append((doc, match["score"]))
    return docs


def _query_single_index(index, vec, top_k):
    """Query a single Pinecone index (for ThreadPoolExecutor)."""
    return index.query(vector=vec, top_k=top_k, include_metadata=True)


def _retrieve_and_prepare(question: str):
    """Shared retrieval logic: embed, search all indexes, dedup, rerank, format context.

    Returns (docs_with_scores, context, timing_dict).
    """
    indexes = _get_pinecone_indexes()

    t0 = time.perf_counter()

    # Check embedding cache — on miss, embed once and cache
    vec = _get_cached_embedding(question)
    if vec is None:
        vec = _get_embeddings().embed_query(question)
        _put_cached_embedding(question, vec)

    # Query all indexes in parallel
    with ThreadPoolExecutor(max_workers=len(indexes)) as executor:
        futures = {
            cb_name: executor.submit(_query_single_index, idx, vec, TOP_K * 2)
            for cb_name, idx in indexes.items()
        }
        all_raw = {
            cb_name: future.result()
            for cb_name, future in futures.items()
        }

    # Merge results from all indexes
    raw_results = []
    for cb_name, results in all_raw.items():
        raw_results.extend(_pinecone_query_to_docs(results, codebase=cb_name))

    # Sort by score descending
    raw_results.sort(key=lambda x: x[1], reverse=True)

    t1 = time.perf_counter()

    deduped = _deduplicate_by_file(raw_results, limit=TOP_K)

    t2 = time.perf_counter()
    reranked = _rerank(question, deduped, top_n=9)
    t3 = time.perf_counter()

    docs = [doc for doc, _ in reranked]
    context = _format_context(docs)

    timing = {
        "pinecone_embed_ms": (t1 - t0) * 1000,
        "rerank_ms": (t3 - t2) * 1000,
    }
    return reranked, context, timing


def _build_sources(reranked: List[Tuple[Document, float]]) -> List[RetrievedChunk]:
    """Convert reranked (doc, score) pairs into RetrievedChunk list."""
    sources: List[RetrievedChunk] = []
    for doc, score in reranked:
        meta = doc.metadata
        chunk = Chunk(
            id=meta.get("id", ""),
            text=doc.page_content,
            file_path=meta.get("file_path", ""),
            start_line=int(meta.get("start_line", 0)),
            end_line=int(meta.get("end_line", 0)),
            chunk_type=meta.get("chunk_type", ""),
            component_name=meta.get("component_name", ""),
            package_name=meta.get("package_name", ""),
            language=meta.get("language", ""),
            codebase=meta.get("codebase", ""),
        )
        sources.append(RetrievedChunk(chunk=chunk, score=score))
    return sources


def query(question: str) -> QueryResult:
    """Execute a query through the full RAG pipeline (non-streaming)."""
    start = time.perf_counter()

    reranked, context, timing = _retrieve_and_prepare(question)

    prompt = _get_prompt()
    llm = _get_llm()
    chain = prompt | llm | StrOutputParser()

    t4 = time.perf_counter()
    answer = chain.invoke({"context": context, "question": question})
    t5 = time.perf_counter()

    elapsed_ms = (time.perf_counter() - start) * 1000
    timing["llm_ms"] = (t5 - t4) * 1000
    timing["total_ms"] = elapsed_ms

    print(
        f"\n  \033[38;5;240m[timing] pinecone+embed={timing['pinecone_embed_ms']:.0f}ms"
        f" | rerank={timing['rerank_ms']:.0f}ms"
        f" | llm={timing['llm_ms']:.0f}ms"
        f" | total={elapsed_ms:.0f}ms\033[0m"
    )

    return QueryResult(
        query=question,
        answer=answer,
        sources=_build_sources(reranked),
        latency_ms=elapsed_ms,
    )


def query_stream(question: str) -> Generator[str | QueryResult, None, None]:
    """Stream the RAG pipeline: yields answer tokens, then a final QueryResult.

    Usage:
        for chunk in query_stream("How does X work?"):
            if isinstance(chunk, str):
                print(chunk, end="", flush=True)
            else:
                # chunk is the final QueryResult
                result = chunk
    """
    start = time.perf_counter()

    reranked, context, timing = _retrieve_and_prepare(question)

    prompt = _get_prompt()
    llm = _get_llm()
    chain = prompt | llm | StrOutputParser()

    t4 = time.perf_counter()
    answer_parts = []
    for token in chain.stream({"context": context, "question": question}):
        answer_parts.append(token)
        yield token
    t5 = time.perf_counter()

    elapsed_ms = (time.perf_counter() - start) * 1000
    timing["llm_ms"] = (t5 - t4) * 1000
    timing["total_ms"] = elapsed_ms

    print(
        f"\n  \033[38;5;240m[timing] pinecone+embed={timing['pinecone_embed_ms']:.0f}ms"
        f" | rerank={timing['rerank_ms']:.0f}ms"
        f" | llm={timing['llm_ms']:.0f}ms"
        f" | total={elapsed_ms:.0f}ms\033[0m"
    )

    yield QueryResult(
        query=question,
        answer="".join(answer_parts),
        sources=_build_sources(reranked),
        latency_ms=elapsed_ms,
    )
