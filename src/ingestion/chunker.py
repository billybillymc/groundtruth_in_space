"""Ada-aware, C-aware, and YAML chunking for multiple codebases."""

import hashlib
import os
import re
from typing import Dict, List

import tiktoken

from src.config import CHUNK_MAX_TOKENS, CHUNK_OVERLAP_RATIO, CHUNK_TARGET_TOKENS
from src.models import Chunk

# tiktoken encoder for accurate token counting
_encoder = tiktoken.get_encoding("cl100k_base")

# Regex patterns for Ada structural boundaries (ordered by priority)
ADA_SPLIT_PATTERNS = re.compile(
    r"|".join([
        r"^\s*package\s+body\s+\w[\w.]*\s+is",
        r"^\s*package\s+\w[\w.]*\s+is",
        r"^\s*(?:overriding\s+)?procedure\s+\w+",
        r"^\s*(?:overriding\s+)?function\s+\w+",
        r"^\s*-{20,}",
        r"^\s*type\s+\w+\s+is",
        r"^\s*private\s*$",
    ]),
    re.IGNORECASE | re.MULTILINE,
)

# Regex patterns for C structural boundaries
C_SPLIT_PATTERNS = re.compile(
    r"|".join([
        r"^(?:static\s+|extern\s+|inline\s+)*(?:void|int|uint\d+|char|bool|float|double|size_t|ssize_t|int32|uint32|CFE_\w+|OS_\w+|osal_\w+)\s+\w+\s*\(",  # function definition
        r"^\s*typedef\s+(?:struct|enum|union)",
        r"^\s*(?:struct|enum|union)\s+\w+",
        r"^\s*/\*[*=\-]{10,}",  # comment separator
        r"^\s*//[/=\-]{10,}",   # line comment separator
        r"^\s*#\s*(?:ifndef|ifdef|if\s)",  # preprocessor guards
    ]),
    re.IGNORECASE | re.MULTILINE,
)


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken."""
    return len(_encoder.encode(text))


def _generate_chunk_id(file_path: str, start_line: int) -> str:
    """Deterministic chunk ID from file path and start line."""
    raw = f"{file_path}:{start_line}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _extract_package_name(content: str) -> str:
    """Extract from first 'package [body] Foo.Bar.Baz is' line."""
    match = re.search(r"package\s+(?:body\s+)?([\w.]+)\s+is", content, re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_component_name(file_path: str) -> str:
    """Extract component name from file path."""
    parts = file_path.replace("\\", "/").split("/")
    for marker in ["components", "types", "core", "data_structures", "util", "unit_test"]:
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts) and not parts[idx + 1].endswith(
                (".ads", ".adb", ".yaml")
            ):
                return parts[idx + 1]
    return ""


def _extract_c_module_name(file_path: str) -> str:
    """Extract module name from C file path (parent directory)."""
    parts = file_path.replace("\\", "/").split("/")
    # Look for meaningful directory markers in cFS
    for marker in ["apps", "modules", "fsw", "src", "cfe", "osal"]:
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts) and not parts[idx + 1].endswith((".c", ".h")):
                return parts[idx + 1]
    # Fallback: parent directory of the file
    if len(parts) >= 2:
        parent = parts[-2]
        if parent not in ("src", "inc", "fsw"):
            return parent
    return ""


def _find_structural_boundaries(lines: List[str], pattern=ADA_SPLIT_PATTERNS) -> List[int]:
    """Return line indices that represent good split points."""
    boundaries = [0]
    for i, line in enumerate(lines):
        if i == 0:
            continue
        if pattern.match(line):
            boundaries.append(i)
    return boundaries


def _merge_small_segments(
    segments: List[Dict], target_tokens: int
) -> List[Dict]:
    """Merge adjacent small segments until they approach target token count."""
    if not segments:
        return segments

    merged: List[Dict] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        combined_tokens = _count_tokens(prev["text"] + seg["text"])
        if combined_tokens <= target_tokens:
            prev["text"] += seg["text"]
            prev["end_line"] = seg["end_line"]
        else:
            merged.append(seg)
    return merged


def _build_chunks_from_segments(
    segments: List[Dict], lines: List[str], rel_path: str, category: str,
    component_name: str, package_name: str, language: str, codebase: str,
) -> List[Chunk]:
    """Build Chunk objects from segments with overlap and hard-split fallback."""
    overlap_lines = max(3, int(len(lines) * CHUNK_OVERLAP_RATIO))
    chunks: List[Chunk] = []

    for i, seg in enumerate(segments):
        text = seg["text"]

        # Add overlap from previous segment
        if i > 0 and overlap_lines > 0:
            prev_text = segments[i - 1]["text"]
            prev_lines = prev_text.splitlines(keepends=True)
            overlap_text = "".join(prev_lines[-overlap_lines:])
            text = overlap_text + text

        # If still too large, do a hard split
        if _count_tokens(text) > CHUNK_MAX_TOKENS:
            sub_chunks = _hard_split(
                text, seg["start_line"], rel_path, category,
                component_name, package_name, language, codebase,
            )
            chunks.extend(sub_chunks)
        else:
            chunks.append(
                Chunk(
                    id=_generate_chunk_id(rel_path, seg["start_line"]),
                    text=text,
                    file_path=rel_path,
                    start_line=seg["start_line"],
                    end_line=seg["end_line"],
                    chunk_type=category,
                    component_name=component_name,
                    package_name=package_name,
                    language=language,
                    codebase=codebase,
                )
            )

    return chunks


def chunk_ada_file(
    file_path: str, rel_path: str, content: str, category: str, codebase: str = "adamant",
) -> List[Chunk]:
    """Chunk an Ada file using structural boundaries."""
    if not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    package_name = _extract_package_name(content)
    component_name = _extract_component_name(file_path)
    language = "ada"

    # Pass 1: If file fits in one chunk, return it whole
    token_count = _count_tokens(content)
    if token_count <= CHUNK_MAX_TOKENS:
        return [
            Chunk(
                id=_generate_chunk_id(rel_path, 1),
                text=content,
                file_path=rel_path,
                start_line=1,
                end_line=len(lines),
                chunk_type=category,
                component_name=component_name,
                package_name=package_name,
                language=language,
                codebase=codebase,
            )
        ]

    # Pass 2: Split at structural boundaries
    boundaries = _find_structural_boundaries(lines, ADA_SPLIT_PATTERNS)

    segments: List[Dict] = []
    for i in range(len(boundaries)):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        text = "".join(lines[start:end])
        segments.append({
            "text": text,
            "start_line": start + 1,  # 1-indexed
            "end_line": end,
        })

    # Merge small segments
    segments = _merge_small_segments(segments, CHUNK_TARGET_TOKENS)

    return _build_chunks_from_segments(
        segments, lines, rel_path, category,
        component_name, package_name, language, codebase,
    )


def chunk_c_file(
    file_path: str, rel_path: str, content: str, category: str, codebase: str = "cfs",
) -> List[Chunk]:
    """Chunk a C file using structural boundaries."""
    if not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    module_name = _extract_c_module_name(file_path)
    language = "c"

    # If file fits in one chunk, return it whole
    token_count = _count_tokens(content)
    if token_count <= CHUNK_MAX_TOKENS:
        return [
            Chunk(
                id=_generate_chunk_id(rel_path, 1),
                text=content,
                file_path=rel_path,
                start_line=1,
                end_line=len(lines),
                chunk_type=category,
                component_name=module_name,
                package_name="",
                language=language,
                codebase=codebase,
            )
        ]

    # Split at structural boundaries
    boundaries = _find_structural_boundaries(lines, C_SPLIT_PATTERNS)

    segments: List[Dict] = []
    for i in range(len(boundaries)):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        text = "".join(lines[start:end])
        segments.append({
            "text": text,
            "start_line": start + 1,
            "end_line": end,
        })

    segments = _merge_small_segments(segments, CHUNK_TARGET_TOKENS)

    return _build_chunks_from_segments(
        segments, lines, rel_path, category,
        module_name, "", language, codebase,
    )


def _hard_split(
    text: str, base_line: int, rel_path: str, category: str,
    component_name: str, package_name: str, language: str, codebase: str,
) -> List[Chunk]:
    """Fall back to line-based splitting for very large segments."""
    lines = text.splitlines(keepends=True)
    chunks: List[Chunk] = []
    current_lines: List[str] = []
    current_start = base_line

    for i, line in enumerate(lines):
        current_lines.append(line)
        if _count_tokens("".join(current_lines)) >= CHUNK_TARGET_TOKENS:
            chunks.append(
                Chunk(
                    id=_generate_chunk_id(rel_path, current_start),
                    text="".join(current_lines),
                    file_path=rel_path,
                    start_line=current_start,
                    end_line=current_start + len(current_lines) - 1,
                    chunk_type=category,
                    component_name=component_name,
                    package_name=package_name,
                    language=language,
                    codebase=codebase,
                )
            )
            current_start = current_start + len(current_lines)
            current_lines = []

    # Remaining lines
    if current_lines:
        chunks.append(
            Chunk(
                id=_generate_chunk_id(rel_path, current_start),
                text="".join(current_lines),
                file_path=rel_path,
                start_line=current_start,
                end_line=current_start + len(current_lines) - 1,
                chunk_type=category,
                component_name=component_name,
                package_name=package_name,
                language=language,
                codebase=codebase,
            )
        )

    return chunks


def chunk_yaml_file(file_path: str, rel_path: str, content: str, codebase: str = "adamant") -> List[Chunk]:
    """Chunk a YAML model file. Most are small enough for a single chunk."""
    if not content.strip():
        return []

    component_name = _extract_component_name(file_path)
    package_name = os.path.splitext(os.path.basename(file_path))[0] if file_path else ""
    line_count = content.count("\n") + 1

    if _count_tokens(content) <= CHUNK_MAX_TOKENS:
        return [
            Chunk(
                id=_generate_chunk_id(rel_path, 1),
                text=content,
                file_path=rel_path,
                start_line=1,
                end_line=line_count,
                chunk_type="model",
                component_name=component_name,
                package_name=package_name,
                language="yaml",
                codebase=codebase,
            )
        ]

    # Split large YAML at top-level keys
    lines = content.splitlines(keepends=True)
    segments: List[Dict] = []
    current_start = 0
    current_lines: List[str] = []

    for i, line in enumerate(lines):
        # Top-level key: line starts with non-space, non-dash, contains ':'
        if i > 0 and re.match(r"^[a-zA-Z_].*:", line) and current_lines:
            segments.append({
                "text": "".join(current_lines),
                "start_line": current_start + 1,
                "end_line": current_start + len(current_lines),
            })
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        segments.append({
            "text": "".join(current_lines),
            "start_line": current_start + 1,
            "end_line": current_start + len(current_lines),
        })

    segments = _merge_small_segments(segments, CHUNK_TARGET_TOKENS)

    return [
        Chunk(
            id=_generate_chunk_id(rel_path, seg["start_line"]),
            text=seg["text"],
            file_path=rel_path,
            start_line=seg["start_line"],
            end_line=seg["end_line"],
            chunk_type="model",
            component_name=component_name,
            package_name=package_name,
            language="yaml",
            codebase=codebase,
        )
        for seg in segments
    ]


def chunk_all_files(files: List[Dict[str, str]]) -> List[Chunk]:
    """Process all discovered files into chunks."""
    all_chunks: List[Chunk] = []

    for file_info in files:
        path = file_info["path"]
        rel_path = file_info["rel_path"]
        category = file_info["category"]
        ext = file_info["extension"]
        codebase = file_info.get("codebase", "adamant")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError) as e:
            print(f"  Warning: Could not read {rel_path}: {e}")
            continue

        if ext in (".ads", ".adb"):
            chunks = chunk_ada_file(path, rel_path, content, category, codebase)
        elif ext == ".yaml":
            chunks = chunk_yaml_file(path, rel_path, content, codebase)
        elif ext in (".c", ".h"):
            chunks = chunk_c_file(path, rel_path, content, category, codebase)
        else:
            continue

        all_chunks.extend(chunks)

    return all_chunks
