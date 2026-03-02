#!/usr/bin/env python3
"""Bulk-ingest .nk files from a folder into the comp pattern library.

Usage:
    uv run python scripts/ingest_nk_folder.py /path/to/nk/folder/
    uv run python scripts/ingest_nk_folder.py /Applications/Nuke17.0v1/Documentation/html/content/example_scripts/

Parses each .nk file with the v2 parser (full connection extraction),
splits into connected components, and stores all patterns with embeddings.
Skips duplicates (same name + source_script already in database).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from nukebread.server.rag.nk_parser import parse_nk_file
from nukebread.server.rag.store import CompPatternStore


def ingest_folder(
    folder_path: str,
    store: CompPatternStore | None = None,
    verbose: bool = True,
) -> dict:
    """Ingest all .nk files from a folder.

    Returns a summary dict with counts.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Directory not found: {folder_path}")

    nk_files = sorted(folder.glob("*.nk"))
    if not nk_files:
        if verbose:
            print(f"No .nk files found in {folder_path}")
        return {"files": 0, "patterns": 0, "errors": 0, "skipped": 0}

    if store is None:
        store = CompPatternStore()

    total_patterns = 0
    total_errors = 0
    total_skipped = 0
    start_time = time.time()

    if verbose:
        print(f"Found {len(nk_files)} .nk files in {folder_path}")
        print()

    for nk_file in nk_files:
        try:
            patterns = parse_nk_file(str(nk_file))

            if not patterns:
                if verbose:
                    print(f"  {nk_file.name}: no patterns extracted")
                continue

            saved = 0
            skipped = 0
            for pattern in patterns:
                try:
                    pid = store.save_pattern(
                        name=pattern["name"],
                        description=pattern["description"],
                        graph_dict=pattern["graph"],
                        category=pattern["category"],
                        source_script=str(nk_file),
                        source_type="nk_import",
                    )
                    saved += 1
                    total_patterns += 1
                except Exception as exc:
                    # Check for duplicate (unique constraint violation)
                    err_str = str(exc).lower()
                    if "unique" in err_str or "duplicate" in err_str:
                        skipped += 1
                        total_skipped += 1
                    else:
                        total_errors += 1
                        if verbose:
                            print(f"  ERROR saving {pattern['name']}: {exc}",
                                  file=sys.stderr)

            if verbose:
                status = f"  {nk_file.name}: {saved} patterns saved"
                if skipped:
                    status += f", {skipped} skipped (duplicate)"
                node_count = sum(
                    len(p["graph"]["nodes"]) for p in patterns
                )
                status += f" ({node_count} total nodes)"
                print(status)

        except Exception as exc:
            total_errors += 1
            if verbose:
                print(f"  ERROR parsing {nk_file.name}: {exc}", file=sys.stderr)

    elapsed = time.time() - start_time

    summary = {
        "files": len(nk_files),
        "patterns": total_patterns,
        "skipped": total_skipped,
        "errors": total_errors,
        "elapsed_seconds": round(elapsed, 1),
    }

    if verbose:
        print()
        stats = store.stats()
        print(f"Done in {elapsed:.1f}s.")
        print(f"  Files processed: {len(nk_files)}")
        print(f"  Patterns saved: {total_patterns}")
        print(f"  Duplicates skipped: {total_skipped}")
        print(f"  Errors: {total_errors}")
        print(f"  Library total: {stats['total_patterns']} patterns, "
              f"{stats['embedded_chunks']} embedded chunks")

    return summary


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_nk_folder.py <folder_path>",
              file=sys.stderr)
        sys.exit(1)

    folder_path = sys.argv[1]
    ingest_folder(folder_path)


if __name__ == "__main__":
    main()
