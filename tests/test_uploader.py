"""Tests for Pinecone upload with mocked client."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from src.ingestion.uploader import (
    load_chunks_cache,
    save_chunks_cache,
    upload_to_pinecone,
)


def test_save_and_load_cache():
    """Cache round-trips correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "cache.json")
        records = [
            {"id": "1", "metadata": {"file_path": "foo.ads", "text": "hello"}},
            {"id": "2", "metadata": {"file_path": "bar.adb", "text": "world"}},
        ]
        save_chunks_cache(records, path)
        loaded = load_chunks_cache(path)
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0]["id"] == "1"


def test_load_cache_returns_none_if_missing():
    """Returns None when cache file doesn't exist."""
    assert load_chunks_cache("/nonexistent/path.json") is None


@patch("src.ingestion.uploader.Pinecone")
def test_upload_batching(mock_pc_cls):
    """Upload should process in batches."""
    mock_index = MagicMock()
    mock_pc_cls.return_value.Index.return_value = mock_index

    records = [
        {"id": f"v{i}", "values": [0.1] * 1536, "metadata": {"text": f"chunk {i}"}}
        for i in range(5)
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.ingestion.uploader._checkpoint_path_for", return_value=os.path.join(tmpdir, "cp.txt")):
            upload_to_pinecone(records, batch_size=2)

    # 5 records / batch_size 2 = 3 batches
    assert mock_index.upsert.call_count == 3


@patch("src.ingestion.uploader.Pinecone")
def test_upload_resume_from_checkpoint(mock_pc_cls):
    """Upload should skip already-completed batches."""
    mock_index = MagicMock()
    mock_pc_cls.return_value.Index.return_value = mock_index

    records = [
        {"id": f"v{i}", "values": [0.1] * 1536, "metadata": {"text": f"chunk {i}"}}
        for i in range(6)
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = os.path.join(tmpdir, "cp.txt")
        # Pretend 2 batches already done
        with open(checkpoint_path, "w") as f:
            f.write("2")

        with patch("src.ingestion.uploader._get_checkpoint", return_value=2):
            with patch("src.ingestion.uploader._save_checkpoint"):
                with patch("src.ingestion.uploader._clear_checkpoint"):
                    upload_to_pinecone(records, batch_size=2)

    # 6 records / 2 = 3 total batches, 2 already done, so 1 remaining
    assert mock_index.upsert.call_count == 1
