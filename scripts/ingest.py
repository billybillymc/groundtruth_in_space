"""Standalone ingestion script: scan -> chunk -> cache -> embed -> upload."""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import CODEBASES
from src.ingestion.scanner import scan_source_files
from src.ingestion.chunker import chunk_all_files
from src.ingestion.embedder import embed_chunks
from src.ingestion.uploader import save_chunks_cache, upload_to_pinecone, _cache_path_for


def ingest_codebase(codebase: str, dry_run: bool = False) -> None:
    """Run the full ingestion pipeline for a single codebase."""
    cb_config = CODEBASES[codebase]
    index_name = cb_config["index"]
    cache_path = _cache_path_for(codebase)

    print("=" * 60)
    print(f"  {codebase.upper()} Ingestion Pipeline")
    print(f"  Index: {index_name}")
    print("=" * 60)

    # Step 1: Scan
    print("\n[1/4] Scanning source files...")
    files = scan_source_files(codebase=codebase)
    print(f"  Found {len(files)} files")

    by_ext = {}
    for f in files:
        ext = f["extension"]
        by_ext[ext] = by_ext.get(ext, 0) + 1
    for ext, count in sorted(by_ext.items()):
        print(f"  {ext}: {count}")

    # Step 2: Chunk
    print("\n[2/4] Chunking files...")
    chunks = chunk_all_files(files)
    print(f"  Generated {len(chunks)} chunks")

    # Step 3: Cache
    print("\n[3/4] Caching chunks...")
    save_chunks_cache([{"id": c.id, "metadata": {
        "text": c.text,
        "file_path": c.file_path,
        "start_line": c.start_line,
        "end_line": c.end_line,
        "chunk_type": c.chunk_type,
        "component_name": c.component_name,
        "package_name": c.package_name,
        "language": c.language,
        "codebase": c.codebase,
    }} for c in chunks], path=cache_path)

    if dry_run:
        print("\n[DRY RUN] Skipping embedding and upload.")
        return

    # Step 4: Embed
    print("\n[3/4] Embedding chunks...")
    records = embed_chunks(chunks)

    # Step 5: Upload
    print("\n[4/4] Uploading to Pinecone...")
    upload_to_pinecone(records, index_name=index_name, codebase=codebase)

    print(f"\n  {codebase.upper()} ingestion complete! {len(records)} vectors indexed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest codebases into Pinecone.")
    parser.add_argument(
        "--codebase",
        choices=["adamant", "cfs", "cubedos", "all"],
        default="all",
        help="Which codebase to ingest (default: all).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and cache chunks without calling APIs.",
    )
    args = parser.parse_args()

    if args.codebase == "all":
        targets = list(CODEBASES.keys())
    else:
        targets = [args.codebase]

    for cb in targets:
        ingest_codebase(cb, dry_run=args.dry_run)
        print()

    print("=" * 60)
    print("  All ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
