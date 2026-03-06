"""OpenAI batch embedding with exponential backoff."""

import time
from typing import Dict, List

from langchain_openai import OpenAIEmbeddings

from src.config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL, OPENAI_API_KEY
from src.models import Chunk


def _create_embeddings_client() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)


def _embed_batch_with_backoff(
    client: OpenAIEmbeddings, texts: List[str], max_retries: int = 5
) -> List[List[float]]:
    """Embed a batch of texts with exponential backoff on rate limits."""
    for attempt in range(max_retries):
        try:
            return client.embed_documents(texts)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                wait_time = min(2 ** attempt, 32)
                print(f"  Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError(f"Failed to embed batch after {max_retries} retries")


def embed_chunks(
    chunks: List[Chunk], batch_size: int = EMBEDDING_BATCH_SIZE
) -> List[Dict]:
    """
    Embed chunks using OpenAI text-embedding-3-small.

    Returns list of dicts ready for Pinecone upsert:
    {"id": str, "values": list[float], "metadata": dict}
    """
    client = _create_embeddings_client()
    records: List[Dict] = []

    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(chunks), batch_size):
        batch = chunks[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        print(f"  Embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        texts = [chunk.text for chunk in batch]
        vectors = _embed_batch_with_backoff(client, texts)

        for chunk, vector in zip(batch, vectors):
            records.append({
                "id": chunk.id,
                "values": vector,
                "metadata": {
                    "text": chunk.text,
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "chunk_type": chunk.chunk_type,
                    "component_name": chunk.component_name,
                    "package_name": chunk.package_name,
                    "language": chunk.language,
                    "codebase": chunk.codebase,
                },
            })

    return records
