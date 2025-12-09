#!/usr/bin/env python3
"""Utility to batch sentences for manual translation."""

import json
import sys
from pathlib import Path


def split_sentences_into_batches(json_path: str, batch_size: int = 50) -> list:
    """Load sentences and split into batches.

    Args:
        json_path: Path to sentences.json
        batch_size: Number of sentences per batch

    Returns:
        List of batches, each containing sentences with their IDs
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        sentences = json.load(f)

    batches = []
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i + batch_size]
        batches.append(batch)

    return batches


def export_batch_to_txt(batch: list, batch_num: int, output_dir: str = "batches"):
    """Export single batch to human-readable text file.

    Args:
        batch: List of sentence dicts with 'id' and 'text'
        batch_num: Batch number
        output_dir: Directory to save batch files
    """
    output_path = Path(output_dir) / f"batch_{batch_num:03d}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"BATCH {batch_num}\n")
        f.write("=" * 80 + "\n\n")

        for item in batch:
            f.write(f"[{item['id']}]\n")
            f.write(f"{item['text']}\n")
            f.write("---\n\n")

    return str(output_path)


def export_batch_to_json(batch: list, batch_num: int, output_dir: str = "batches"):
    """Export single batch to JSON for AI translation.

    Args:
        batch: List of sentence dicts
        batch_num: Batch number
        output_dir: Directory to save batch files
    """
    output_path = Path(output_dir) / f"batch_{batch_num:03d}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)

    return str(output_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_translator.py <sentences.json> [batch_size]")
        print("  Default batch_size: 50")
        sys.exit(1)

    json_path = sys.argv[1]
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    if not Path(json_path).exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    print(f"Loading sentences from {json_path}...")
    batches = split_sentences_into_batches(json_path, batch_size)

    print(f"Total sentences: {sum(len(b) for b in batches)}")
    print(f"Batch size: {batch_size}")
    print(f"Total batches: {len(batches)}\n")

    # Export all batches
    for i, batch in enumerate(batches):
        txt_file = export_batch_to_txt(batch, i)
        json_file = export_batch_to_json(batch, i)
        print(f"  Batch {i:3d}: {len(batch):3d} sentences → {json_file}")


if __name__ == "__main__":
    main()
