# GroundTruth

**Author:** William Gardner McIntyre
**License:** MIT

GroundTruth is a RAG-based (Retrieval-Augmented Generation) tool for exploring and understanding legacy flight software codebases. It ingests source code, chunks and embeds it into a vector store, and provides a conversational interface for asking questions about the code.

Currently supports three open-source flight software frameworks:

- **Adamant** -- Ada component-based flight software framework
- **cFS** (core Flight System) -- NASA's C-based flight software framework
- **CubeDOS** -- Ada framework for CubeSat missions

## How it works

1. **Ingestion** -- Source files are scanned, chunked with overlap, embedded via OpenAI, and uploaded to Pinecone.
2. **Retrieval** -- User queries are embedded and matched against the vector store. Results are reranked with Cohere.
3. **Synthesis** -- Retrieved chunks are fed to Google Gemini with a tailored prompt to produce grounded answers with source citations.

## Prerequisites

- Python 3.11+
- API keys for: OpenAI (embeddings), Pinecone (vector store), Google Gemini (LLM), and optionally Cohere (reranking) and LangSmith (tracing)

## Setup

Clone with submodules to pull in the source codebases:

```
git clone --recurse-submodules https://github.com/billybillymc/groundtruth_in_space.git
cd groundtruth_in_space
```

If you already cloned without submodules:

```
git submodule update --init --recursive
```

Create a virtual environment and install dependencies:

```
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example environment file and fill in your API keys:

```
cp .env.example .env
```

Required variables:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Embeddings (text-embedding-3-small) |
| `PINECONE_API_KEY` | Vector store |
| `PINECONE_INDEX_NAME` | Pinecone index name (default: `groundtruth`) |
| `GOOGLE_API_KEY` | Gemini LLM for answer generation |
| `COHERE_API_KEY` | (Optional) Reranking |
| `LANGSMITH_API_KEY` | (Optional) LangSmith tracing |

## Ingestion

Before querying, you need to ingest at least one codebase:

```
# Ingest all three codebases
python -m scripts.ingest

# Ingest a specific codebase
python -m scripts.ingest --codebase adamant
python -m scripts.ingest --codebase cfs
python -m scripts.ingest --codebase cubedos

# Dry run (parse and cache chunks without calling APIs)
python -m scripts.ingest --dry-run
```

## Usage

### CLI

Interactive terminal interface with streaming answers, source citations, and a rocket animation:

```
python -m src.cli
```

Commands inside the CLI:

- Type a number to pick a suggested question
- Type any natural-language question
- `/help` -- show help
- `/criticize` -- submit feedback on the last answer
- `/quit` -- exit

### Web

A FastAPI WebSocket server that serves a browser-based terminal interface:

```
uvicorn src.web.server:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in your browser. The frontend files in `frontend/` are served automatically.

### Docker

```
docker build -t groundtruth .
docker run -p 8000:8000 --env-file .env groundtruth
```

## Project structure

```
src/
  cli.py              # Terminal UI
  config.py           # Environment and settings
  models.py           # Data models
  ingestion/
    scanner.py        # Source file discovery
    chunker.py        # AST-aware chunking
    embedder.py       # OpenAI embedding
    uploader.py       # Pinecone upload
  retrieval/
    retriever.py      # Vector search + reranking
  synthesis/
    chain.py          # LLM chain with streaming
    prompts.py        # Prompt templates
  web/
    server.py         # FastAPI WebSocket server
    session.py        # Per-connection session logic
    terminal_io.py    # Terminal rendering for web
  feedback/
    store.py          # SQLite feedback storage
frontend/
  index.html          # Web terminal UI
  style.css
  terminal.js
scripts/
  ingest.py           # Ingestion CLI
  bench.py            # Benchmarking
  eval_rerank.py      # Reranker evaluation
evals/
  evaluator.py        # Eval harness
  suites/             # YAML eval suites
tests/
  test_*.py           # Unit tests
```

## Evals

Run the evaluation suite:

```
python -m evals
```

Eval suites are defined as YAML files in `evals/suites/`. Results are written to `evals/results/`.

## Tests

```
pytest
```
