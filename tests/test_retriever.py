"""Tests for retrieval with mocked Pinecone."""

from unittest.mock import MagicMock, patch


@patch("src.retrieval.retriever._get_indexes")
@patch("src.retrieval.retriever._get_embeddings")
def test_retrieve_returns_chunks(mock_embeddings, mock_indexes):
    """Retrieve should return RetrievedChunk objects from multiple indexes."""
    from src.retrieval.retriever import retrieve

    mock_emb_instance = MagicMock()
    mock_emb_instance.embed_query.return_value = [0.1] * 1536
    mock_embeddings.return_value = mock_emb_instance

    mock_adamant_idx = MagicMock()
    mock_adamant_idx.query.return_value = {
        "matches": [
            {
                "id": "chunk1",
                "score": 0.95,
                "metadata": {
                    "text": "package Foo is end Foo;",
                    "file_path": "adamant/src/types/foo/foo.ads",
                    "start_line": 1,
                    "end_line": 3,
                    "chunk_type": "spec",
                    "component_name": "foo",
                    "package_name": "Foo",
                    "language": "ada",
                    "codebase": "adamant",
                },
            }
        ]
    }
    mock_cfs_idx = MagicMock()
    mock_cfs_idx.query.return_value = {"matches": []}
    mock_cubedos_idx = MagicMock()
    mock_cubedos_idx.query.return_value = {"matches": []}

    mock_indexes.return_value = {
        "adamant": mock_adamant_idx,
        "cfs": mock_cfs_idx,
        "cubedos": mock_cubedos_idx,
    }

    results = retrieve("What is Foo?")
    assert len(results) == 1
    assert results[0].score == 0.95
    assert results[0].chunk.file_path == "adamant/src/types/foo/foo.ads"
    assert results[0].chunk.codebase == "adamant"


@patch("src.retrieval.retriever._get_indexes")
@patch("src.retrieval.retriever._get_embeddings")
def test_retrieve_merges_across_indexes(mock_embeddings, mock_indexes):
    """Retrieve should merge results from all indexes by score."""
    from src.retrieval.retriever import retrieve

    mock_emb_instance = MagicMock()
    mock_emb_instance.embed_query.return_value = [0.1] * 1536
    mock_embeddings.return_value = mock_emb_instance

    mock_adamant_idx = MagicMock()
    mock_adamant_idx.query.return_value = {
        "matches": [
            {
                "id": "adamant1",
                "score": 0.80,
                "metadata": {
                    "text": "package Foo is end Foo;",
                    "file_path": "adamant/src/foo.ads",
                    "start_line": 1, "end_line": 3,
                    "chunk_type": "spec", "component_name": "foo",
                    "package_name": "Foo", "language": "ada",
                    "codebase": "adamant",
                },
            }
        ]
    }
    mock_cfs_idx = MagicMock()
    mock_cfs_idx.query.return_value = {
        "matches": [
            {
                "id": "cfs1",
                "score": 0.90,
                "metadata": {
                    "text": "void CFE_ES_Main(void) {}",
                    "file_path": "cFS/cfe/fsw/src/cfe_es_task.c",
                    "start_line": 1, "end_line": 5,
                    "chunk_type": "source", "component_name": "cfe",
                    "package_name": "", "language": "c",
                    "codebase": "cfs",
                },
            }
        ]
    }
    mock_cubedos_idx = MagicMock()
    mock_cubedos_idx.query.return_value = {"matches": []}

    mock_indexes.return_value = {
        "adamant": mock_adamant_idx,
        "cfs": mock_cfs_idx,
        "cubedos": mock_cubedos_idx,
    }

    results = retrieve("How does commanding work?", top_k=5)
    assert len(results) == 2
    # cFS result should be first (higher score)
    assert results[0].chunk.codebase == "cfs"
    assert results[1].chunk.codebase == "adamant"


@patch("src.retrieval.retriever._get_indexes")
@patch("src.retrieval.retriever._get_embeddings")
def test_retrieve_empty_results(mock_embeddings, mock_indexes):
    """Retrieve should handle empty results gracefully."""
    from src.retrieval.retriever import retrieve

    mock_emb_instance = MagicMock()
    mock_emb_instance.embed_query.return_value = [0.1] * 1536
    mock_embeddings.return_value = mock_emb_instance

    empty_idx = MagicMock()
    empty_idx.query.return_value = {"matches": []}
    mock_indexes.return_value = {
        "adamant": empty_idx,
        "cfs": empty_idx,
        "cubedos": empty_idx,
    }

    results = retrieve("something obscure")
    assert len(results) == 0
