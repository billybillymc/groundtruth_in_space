"""File discovery: walk source trees, filter by extension, classify files."""

import os
from typing import Dict, List

from src.config import ADAMANT_SRC_PATH, CODEBASES, SKIP_DIRS


def _classify_ada_file(file_path: str) -> str:
    """Classify an Ada file into a chunk_type based on naming patterns."""
    name = os.path.basename(file_path)
    if "_tests-implementation" in name or name == "test.adb":
        return "test"
    if "-tester." in name:
        return "tester"
    if name.endswith("_types.ads"):
        return "types"
    if name.endswith(".yaml"):
        return "model"
    if name.endswith(".ads"):
        return "spec"
    if name.endswith(".adb"):
        return "body"
    return "other"


def _classify_c_file(file_path: str) -> str:
    """Classify a C file into a chunk_type."""
    name = os.path.basename(file_path)
    if name.endswith(".h"):
        return "header"
    if name.endswith(".c"):
        return "source"
    return "other"


def scan_source_files(
    base_path: str = None,
    codebase: str = "adamant",
) -> List[Dict[str, str]]:
    """
    Discover all indexable files under a codebase source path.

    Returns list of dicts with keys: path, rel_path, extension, category, codebase.
    If base_path is given, it overrides the config lookup.
    """
    cb_config = CODEBASES.get(codebase)
    if cb_config:
        if base_path is None:
            base_path = cb_config["src_path"]
        valid_extensions = cb_config["extensions"]
        skip_dirs = cb_config["skip_dirs"]
        language = cb_config["language"]
    else:
        if base_path is None:
            base_path = ADAMANT_SRC_PATH
        valid_extensions = {".ads", ".adb", ".yaml"}
        skip_dirs = SKIP_DIRS
        language = "ada"

    results: List[Dict[str, str]] = []

    for root, dirs, files in os.walk(base_path):
        # Skip excluded directories in-place
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in valid_extensions:
                continue

            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, os.path.dirname(base_path))
            rel_path = rel_path.replace("\\", "/")

            if language == "c":
                category = _classify_c_file(filename)
            else:
                category = _classify_ada_file(filename)

            results.append({
                "path": full_path,
                "rel_path": rel_path,
                "extension": ext,
                "category": category,
                "codebase": codebase,
            })

    return results
