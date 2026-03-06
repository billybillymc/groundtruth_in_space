"""Pinecone similarity search across multiple indexes."""

from concurrent.futures import ThreadPoolExecutor
from typing import List

from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone

from src.config import (
    CODEBASES,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    TOP_K,
)
from src.models import Chunk, RetrievedChunk

# Module-level singletons (initialized on first use)
_embeddings = None
_indexes = None


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)
    return _embeddings


def _get_indexes() -> dict:
    """Return dict of {codebase_name: pinecone_index} for all codebases."""
    global _indexes
    if _indexes is None:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _indexes = {}
        for cb_name, cb_config in CODEBASES.items():
            _indexes[cb_name] = pc.Index(cb_config["index"])
    return _indexes


def _query_single_index(index, query_vector, top_k):
    """Query a single Pinecone index."""
    return index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )


def retrieve(query: str, top_k: int = TOP_K) -> List[RetrievedChunk]:
    """
    Embed the query, search all Pinecone indexes in parallel,
    merge results by score, return top-k.
    """
    embeddings = _get_embeddings()
    indexes = _get_indexes()

    # Embed the query
    query_vector = embeddings.embed_query(query)

    # Fan out across all indexes in parallel
    with ThreadPoolExecutor(max_workers=len(indexes)) as executor:
        futures = {
            cb_name: executor.submit(_query_single_index, idx, query_vector, top_k)
            for cb_name, idx in indexes.items()
        }
        all_results = {
            cb_name: future.result()
            for cb_name, future in futures.items()
        }

    # Merge all results
    retrieved: List[RetrievedChunk] = []
    for cb_name, results in all_results.items():
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            chunk = Chunk(
                id=match["id"],
                text=meta.get("text", ""),
                file_path=meta.get("file_path", ""),
                start_line=int(meta.get("start_line", 0)),
                end_line=int(meta.get("end_line", 0)),
                chunk_type=meta.get("chunk_type", ""),
                component_name=meta.get("component_name", ""),
                package_name=meta.get("package_name", ""),
                language=meta.get("language", ""),
                codebase=meta.get("codebase", cb_name),
            )
            retrieved.append(RetrievedChunk(chunk=chunk, score=match["score"]))

    # Sort by score descending and return top-k
    retrieved.sort(key=lambda x: x.score, reverse=True)
    return retrieved[:top_k]
