"""Pinecone upsert with checkpointing and resume."""

import json
import os
import time
from typing import Dict, List, Optional

from pinecone import Pinecone

from src.config import (
    CHUNKS_CACHE_PATH,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_UPSERT_BATCH,
    UPLOAD_CHECKPOINT_PATH,
)

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cache_path_for(codebase: str) -> str:
    """Return the chunks cache path for a given codebase."""
    if codebase == "adamant":
        return CHUNKS_CACHE_PATH
    return os.path.join(_project_root, "data", f"chunks_cache_{codebase}.json")


def _checkpoint_path_for(codebase: str) -> str:
    """Return the upload checkpoint path for a given codebase."""
    if codebase == "adamant":
        return UPLOAD_CHECKPOINT_PATH
    return os.path.join(_project_root, "data", f"upload_checkpoint_{codebase}.txt")


def save_chunks_cache(records: List[Dict], path: str = CHUNKS_CACHE_PATH) -> None:
    """Save embedded chunks to local JSON cache."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Save without vectors to keep file size reasonable
    cache_data = []
    for r in records:
        cache_data.append({
            "id": r["id"],
            "metadata": r["metadata"],
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)
    print(f"  Cached {len(cache_data)} records to {path}")


def load_chunks_cache(path: str = CHUNKS_CACHE_PATH) -> Optional[List[Dict]]:
    """Load cached chunks if they exist."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_checkpoint(path: str = UPLOAD_CHECKPOINT_PATH) -> int:
    """Read the last successfully uploaded batch index."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return int(f.read().strip())
    return 0


def _save_checkpoint(batch_idx: int, path: str = UPLOAD_CHECKPOINT_PATH) -> None:
    """Save the last successfully uploaded batch index."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(batch_idx))


def _clear_checkpoint(path: str = UPLOAD_CHECKPOINT_PATH) -> None:
    """Remove checkpoint file after successful upload."""
    if os.path.exists(path):
        os.remove(path)


def upload_to_pinecone(
    records: List[Dict],
    index_name: str = PINECONE_INDEX_NAME,
    codebase: str = "adamant",
    batch_size: int = PINECONE_UPSERT_BATCH,
    max_retries: int = 3,
) -> None:
    """
    Upsert records to Pinecone in batches.
    Tracks which batches succeeded via a checkpoint file.
    On failure, can resume from last successful batch.
    """
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(index_name)

    checkpoint_path = _checkpoint_path_for(codebase)
    total_batches = (len(records) + batch_size - 1) // batch_size
    start_batch = _get_checkpoint(checkpoint_path)

    if start_batch > 0:
        print(f"  Resuming from batch {start_batch + 1}/{total_batches}")

    for batch_num in range(start_batch, total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(records))
        batch = records[start_idx:end_idx]

        vectors = [
            {"id": r["id"], "values": r["values"], "metadata": r["metadata"]}
            for r in batch
        ]

        for attempt in range(max_retries):
            try:
                index.upsert(vectors=vectors)
                print(f"  Uploaded batch {batch_num + 1}/{total_batches} ({len(vectors)} vectors)")
                _save_checkpoint(batch_num + 1, checkpoint_path)
                break
            except Exception as e:
                wait_time = min(2 ** attempt, 16)
                print(f"  Upload failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"  Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Failed to upload batch {batch_num + 1} after {max_retries} retries. "
                        f"Resume will start from batch {batch_num + 1}."
                    )

    _clear_checkpoint(checkpoint_path)
    print(f"  Upload complete: {len(records)} vectors in Pinecone index '{index_name}'.")
