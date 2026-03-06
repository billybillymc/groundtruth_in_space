"""Tests for embedding with mocked OpenAI."""

from unittest.mock import MagicMock, patch

from src.ingestion.embedder import embed_chunks


def test_embed_chunks_returns_correct_format(sample_chunks):
    """Embedded chunks should be in Pinecone upsert format."""
    with patch("src.ingestion.embedder._create_embeddings_client") as mock_create:
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [[0.1] * 1536] * len(sample_chunks)
        mock_create.return_value = mock_client

        records = embed_chunks(sample_chunks, batch_size=10)

    assert len(records) == len(sample_chunks)
    for record in records:
        assert "id" in record
        assert "values" in record
        assert "metadata" in record
        assert len(record["values"]) == 1536
        assert "file_path" in record["metadata"]
        assert "text" in record["metadata"]
        assert "start_line" in record["metadata"]


def test_embed_chunks_batching(sample_chunks):
    """Embedding should process in batches."""
    with patch("src.ingestion.embedder._create_embeddings_client") as mock_create:
        mock_client = MagicMock()
        # Return correct number of vectors for each batch
        mock_client.embed_documents.side_effect = lambda texts: [[0.1] * 1536] * len(texts)
        mock_create.return_value = mock_client

        records = embed_chunks(sample_chunks, batch_size=2)

    assert len(records) == 5
    # With 5 chunks and batch_size=2, we should have 3 batches
    assert mock_client.embed_documents.call_count == 3


def test_embed_chunks_retries_on_rate_limit(sample_chunks):
    """Should retry with backoff on rate limit errors."""
    with patch("src.ingestion.embedder._create_embeddings_client") as mock_create:
        with patch("src.ingestion.embedder.time.sleep") as mock_sleep:
            mock_client = MagicMock()
            # Fail once with rate limit, then succeed
            mock_client.embed_documents.side_effect = [
                Exception("429 rate limit exceeded"),
                [[0.1] * 1536] * len(sample_chunks),
            ]
            mock_create.return_value = mock_client

            records = embed_chunks(sample_chunks, batch_size=10)

    assert len(records) == len(sample_chunks)
    mock_sleep.assert_called_once()
