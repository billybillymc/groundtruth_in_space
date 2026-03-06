"""Central configuration loaded from .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise ValueError(f"Missing required environment variable: {key}. Check your .env file.")
    return val


# Required API keys
OPENAI_API_KEY: str = _require_env("OPENAI_API_KEY")
PINECONE_API_KEY: str = _require_env("PINECONE_API_KEY")
GOOGLE_API_KEY: str = _require_env("GOOGLE_API_KEY")

# Optional — only needed for LangSmith tracing
LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")

# Optional
COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")

# Pinecone
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "groundtruth")

# LangSmith
LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "groundtruth")

# Model settings
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIMENSIONS: int = 1536
LLM_MODEL: str = "gemini-2.5-flash"

# Chunking
CHUNK_MAX_TOKENS: int = 1000
CHUNK_TARGET_TOKENS: int = 600
CHUNK_OVERLAP_RATIO: float = 0.15

# Retrieval
TOP_K: int = 10

# Batch sizes
EMBEDDING_BATCH_SIZE: int = 100
PINECONE_UPSERT_BATCH: int = 100

# Paths
ADAMANT_SRC_PATH: str = str(_project_root / "adamant" / "src")
CFS_SRC_PATH: str = str(_project_root / "cFS")
CUBEDOS_SRC_PATH: str = str(_project_root / "cubedos" / "src")
CHUNKS_CACHE_PATH: str = str(_project_root / "data" / "chunks_cache.json")
UPLOAD_CHECKPOINT_PATH: str = str(_project_root / "data" / "upload_checkpoint.txt")
FEEDBACK_DB_PATH: str = str(_project_root / "feedback.db")

# Directories to skip during scanning
SKIP_DIRS: set = {"gen", "doc"}

# Multi-codebase configuration
CODEBASES = {
    "adamant": {
        "src_path": ADAMANT_SRC_PATH,
        "index": "groundtruth",
        "language": "ada",
        "extensions": {".ads", ".adb", ".yaml"},
        "skip_dirs": {"gen", "doc"},
    },
    "cfs": {
        "src_path": CFS_SRC_PATH,
        "index": "groundtruth-cfs",
        "language": "c",
        "extensions": {".c", ".h"},
        "skip_dirs": {"build", "unit-test-coverage", ".git", "ut-stubs", "ut_stubs"},
    },
    "cubedos": {
        "src_path": CUBEDOS_SRC_PATH,
        "index": "groundtruth-cubedos",
        "language": "ada",
        "extensions": {".ads", ".adb"},
        "skip_dirs": {"doc", ".git"},
    },
}
