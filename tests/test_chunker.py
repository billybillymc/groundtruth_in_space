"""Tests for Ada-aware chunker."""

from src.ingestion.chunker import (
    _count_tokens,
    _extract_component_name,
    _extract_package_name,
    chunk_ada_file,
    chunk_all_files,
    chunk_yaml_file,
)


def test_count_tokens():
    """Token counting returns a positive integer."""
    assert _count_tokens("hello world") > 0
    assert _count_tokens("") == 0


def test_extract_package_name():
    assert _extract_package_name("package Foo.Bar is") == "Foo.Bar"
    assert _extract_package_name("package body Foo.Bar is") == "Foo.Bar"
    assert _extract_package_name("no package here") == ""


def test_extract_component_name():
    assert _extract_component_name("adamant/src/components/ccsds_echo/foo.ads") == "ccsds_echo"
    assert _extract_component_name("adamant/src/types/basic_types/foo.ads") == "basic_types"
    assert _extract_component_name("adamant/src/core/component/foo.ads") == "component"
    assert _extract_component_name("random/path/foo.ads") == ""


def test_small_file_single_chunk(sample_ada_spec):
    """Small files should produce exactly one chunk."""
    chunks = chunk_ada_file(
        "/fake/path/foo.ads", "adamant/src/types/foo/foo.ads", sample_ada_spec, "spec"
    )
    assert len(chunks) == 1
    assert chunks[0].file_path == "adamant/src/types/foo/foo.ads"
    assert chunks[0].start_line == 1
    assert chunks[0].chunk_type == "spec"
    assert chunks[0].language == "ada"


def test_small_body_single_chunk(sample_ada_body):
    """Small body file should produce one chunk."""
    chunks = chunk_ada_file(
        "/fake/components/ccsds_echo/impl.adb",
        "adamant/src/components/ccsds_echo/impl.adb",
        sample_ada_body,
        "body",
    )
    assert len(chunks) == 1
    assert chunks[0].package_name == "Component.Ccsds_Echo.Implementation"


def test_large_file_splits(sample_large_ada):
    """Large files should be split into multiple chunks."""
    chunks = chunk_ada_file(
        "/fake/components/large/impl.adb",
        "adamant/src/components/large/impl.adb",
        sample_large_ada,
        "body",
    )
    assert len(chunks) > 1
    # All chunks should have valid metadata
    for chunk in chunks:
        assert chunk.file_path == "adamant/src/components/large/impl.adb"
        assert chunk.start_line > 0
        assert chunk.end_line >= chunk.start_line
        assert chunk.language == "ada"


def test_chunk_has_all_metadata(sample_ada_spec):
    """Chunks should have all required metadata fields."""
    chunks = chunk_ada_file(
        "/fake/types/basic_types/basic_types.ads",
        "adamant/src/types/basic_types/basic_types.ads",
        sample_ada_spec,
        "spec",
    )
    chunk = chunks[0]
    assert chunk.id  # non-empty
    assert chunk.text  # non-empty
    assert chunk.file_path
    assert chunk.start_line >= 1
    assert chunk.end_line >= 1
    assert chunk.chunk_type == "spec"
    assert chunk.language == "ada"


def test_yaml_single_chunk(sample_yaml):
    """Small YAML files should produce one chunk."""
    chunks = chunk_yaml_file(
        "/fake/components/echo/echo.component.yaml",
        "adamant/src/components/echo/echo.component.yaml",
        sample_yaml,
    )
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "model"
    assert chunks[0].language == "yaml"


def test_empty_file_no_chunks():
    """Empty files should produce no chunks."""
    assert chunk_ada_file("/f", "f", "", "spec") == []
    assert chunk_ada_file("/f", "f", "   \n  ", "spec") == []
    assert chunk_yaml_file("/f", "f", "") == []


def test_chunk_ids_are_deterministic(sample_ada_spec):
    """Same input should produce same chunk IDs."""
    chunks1 = chunk_ada_file("/f", "adamant/src/f.ads", sample_ada_spec, "spec")
    chunks2 = chunk_ada_file("/f", "adamant/src/f.ads", sample_ada_spec, "spec")
    assert chunks1[0].id == chunks2[0].id


def test_chunk_all_files():
    """Integration test: chunk_all_files processes a list of file dicts."""
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmpdir:
        ada_path = os.path.join(tmpdir, "test.ads")
        with open(ada_path, "w") as f:
            f.write("package Test is\nend Test;\n")

        files = [{
            "path": ada_path,
            "rel_path": "adamant/src/test.ads",
            "extension": ".ads",
            "category": "spec",
            "codebase": "adamant",
        }]
        chunks = chunk_all_files(files)
        assert len(chunks) == 1
        assert chunks[0].package_name == "Test"
