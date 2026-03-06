"""Data models for LegacyLens."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Chunk:
    """A parsed chunk of source code or YAML, ready for embedding."""
    id: str
    text: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str  # "spec" | "body" | "test" | "tester" | "model" | "types" | "header" | "source"
    component_name: str
    package_name: str
    language: str  # "ada" | "yaml" | "c"
    codebase: str = ""  # "adamant" | "cfs" | "cubedos"


@dataclass
class RetrievedChunk:
    """A chunk returned from Pinecone with similarity score."""
    chunk: Chunk
    score: float


@dataclass
class QueryResult:
    """Complete query response."""
    query: str
    answer: str
    sources: List[RetrievedChunk]
    latency_ms: float
