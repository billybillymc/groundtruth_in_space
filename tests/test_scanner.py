"""Tests for file scanner."""

import os
import tempfile

from src.ingestion.scanner import _classify_ada_file, _classify_c_file, scan_source_files


def test_classify_spec():
    assert _classify_ada_file("component-foo-implementation.ads") == "spec"
    assert _classify_ada_file("foo.ads") == "spec"


def test_classify_body():
    assert _classify_ada_file("component-foo-implementation.adb") == "body"
    assert _classify_ada_file("foo.adb") == "body"


def test_classify_test():
    assert _classify_ada_file("foo_tests-implementation.adb") == "test"
    assert _classify_ada_file("test.adb") == "test"


def test_classify_tester():
    assert _classify_ada_file("component-foo-implementation-tester.ads") == "tester"


def test_classify_types():
    assert _classify_ada_file("foo_types.ads") == "types"


def test_classify_model():
    assert _classify_ada_file("foo.component.yaml") == "model"


def test_classify_c_files():
    assert _classify_c_file("cfe_es_task.c") == "source"
    assert _classify_c_file("cfe_es.h") == "header"


def test_scan_finds_ada_and_yaml():
    """Scan the real Adamant codebase and verify we find files."""
    files = scan_source_files(codebase="adamant")
    assert len(files) > 1000

    extensions = {f["extension"] for f in files}
    assert ".ads" in extensions
    assert ".adb" in extensions
    assert ".yaml" in extensions

    # All files should be tagged with adamant codebase
    assert all(f.get("codebase") == "adamant" for f in files)


def test_scan_skips_gen_directory():
    """Verify gen/ directory is excluded."""
    files = scan_source_files(codebase="adamant")
    gen_files = [f for f in files if "/gen/" in f["rel_path"]]
    assert len(gen_files) == 0


def test_scan_has_required_fields():
    """Each file entry has all required fields."""
    files = scan_source_files(codebase="adamant")
    for f in files[:10]:
        assert "path" in f
        assert "rel_path" in f
        assert "extension" in f
        assert "category" in f
        assert "codebase" in f


def test_scan_cfs_finds_c_files():
    """Scan the cFS codebase and verify we find C files."""
    files = scan_source_files(codebase="cfs")
    assert len(files) > 100
    extensions = {f["extension"] for f in files}
    assert ".c" in extensions
    assert ".h" in extensions
    assert all(f.get("codebase") == "cfs" for f in files)


def test_scan_cubedos_finds_ada_files():
    """Scan the CubeDOS codebase and verify we find Ada files."""
    files = scan_source_files(codebase="cubedos")
    assert len(files) > 10
    extensions = {f["extension"] for f in files}
    assert ".ads" in extensions
    assert ".adb" in extensions
    assert all(f.get("codebase") == "cubedos" for f in files)


def test_scan_with_temp_directory():
    """Test scanner with a controlled temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        os.makedirs(os.path.join(tmpdir, "components", "foo"))
        with open(os.path.join(tmpdir, "components", "foo", "foo.ads"), "w") as f:
            f.write("package Foo is end Foo;")
        with open(os.path.join(tmpdir, "components", "foo", "foo.adb"), "w") as f:
            f.write("package body Foo is end Foo;")
        with open(os.path.join(tmpdir, "components", "foo", "foo.component.yaml"), "w") as f:
            f.write("description: test")

        # Also create a file that should be skipped
        os.makedirs(os.path.join(tmpdir, "gen"))
        with open(os.path.join(tmpdir, "gen", "skip.ads"), "w") as f:
            f.write("skip me")

        files = scan_source_files(tmpdir, codebase="adamant")
        assert len(files) == 3
        assert all("/gen/" not in f["rel_path"] for f in files)
