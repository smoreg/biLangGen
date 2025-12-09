#!/usr/bin/env python3
"""Align Russian and English sentences using existing TextSplitter.

Uses the project's TextSplitter for consistent sentence splitting,
then aligns sentences using OpenAI embeddings for semantic similarity.
"""

import sys
from pathlib import Path
from typing import Optional
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.text_splitter import TextSplitter


def load_and_split(filepath: Path, lang: str, max_length: int = 1000000) -> list[str]:
    """Load file and split into sentences using TextSplitter."""
    text = filepath.read_text(encoding='utf-8')
    splitter = TextSplitter(lang, max_sentence_length=max_length)
    sentences = splitter.split(text)
    return sentences  # TextSplitter returns list[str]


def get_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Get embeddings using free local sentence-transformers model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("ERROR: sentence-transformers not installed!")
        print("Install with: pip install sentence-transformers")
        return []

    # Use multilingual model that works for both Russian and English
    print("    Loading multilingual model (first time may download ~500MB)...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"    Embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}...")
        embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.extend(embeddings.tolist())

    return all_embeddings


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_align(ru_sentences: list[str], en_sentences: list[str],
                   threshold: float = 0.5) -> list[tuple[str, str, float]]:
    """Align sentences using OpenAI embeddings.

    Returns list of (ru, en, similarity_score) tuples.
    """
    if not ru_sentences or not en_sentences:
        return []

    print("  Getting RU embeddings...")
    ru_embeddings = get_embeddings(ru_sentences)

    print("  Getting EN embeddings...")
    en_embeddings = get_embeddings(en_sentences)

    print("  Finding best matches...")
    aligned = []
    used_en = set()

    # For each RU sentence, find best matching EN sentence
    for i, ru_emb in enumerate(ru_embeddings):
        best_j = None
        best_sim = -1

        # Search in a window around expected position (based on ratio)
        expected_j = int(i * len(en_sentences) / len(ru_sentences))
        window = max(20, len(en_sentences) // 10)  # 10% window or at least 20

        start_j = max(0, expected_j - window)
        end_j = min(len(en_sentences), expected_j + window)

        for j in range(start_j, end_j):
            if j in used_en:
                continue
            sim = cosine_similarity(ru_emb, en_embeddings[j])
            if sim > best_sim:
                best_sim = sim
                best_j = j

        if best_j is not None and best_sim >= threshold:
            aligned.append((ru_sentences[i], en_sentences[best_j], best_sim))
            used_en.add(best_j)
        else:
            aligned.append((ru_sentences[i], "", 0.0))

    return aligned


def simple_align(ru_sentences: list[str], en_sentences: list[str]) -> list[tuple[str, str, float]]:
    """Simple 1:1 alignment by position."""
    aligned = []
    min_len = min(len(ru_sentences), len(en_sentences))

    for i in range(min_len):
        aligned.append((ru_sentences[i], en_sentences[i], 1.0))

    if len(ru_sentences) > min_len:
        for i in range(min_len, len(ru_sentences)):
            aligned.append((ru_sentences[i], "", 0.0))

    return aligned


def ratio_based_align(ru_sentences: list[str], en_sentences: list[str]) -> list[tuple[str, str, float]]:
    """Align based on character position ratio."""
    if not ru_sentences or not en_sentences:
        return []

    ru_total = sum(len(s) for s in ru_sentences)
    en_total = sum(len(s) for s in en_sentences)

    ru_positions = []
    cumsum = 0
    for s in ru_sentences:
        ru_positions.append(cumsum / ru_total if ru_total > 0 else 0)
        cumsum += len(s)

    en_positions = []
    cumsum = 0
    for s in en_sentences:
        en_positions.append(cumsum / en_total if en_total > 0 else 0)
        cumsum += len(s)

    aligned = []
    used_en = set()

    for i, ru_pos in enumerate(ru_positions):
        best_j = None
        best_diff = float('inf')

        for j, en_pos in enumerate(en_positions):
            if j not in used_en:
                diff = abs(ru_pos - en_pos)
                if diff < best_diff:
                    best_diff = diff
                    best_j = j

        if best_j is not None and best_diff < 0.05:
            aligned.append((ru_sentences[i], en_sentences[best_j], 1.0 - best_diff))
            used_en.add(best_j)
        else:
            aligned.append((ru_sentences[i], "", 0.0))

    return aligned


def align_chapter(ru_file: Path, en_file: Path, method: str = "embedding",
                 threshold: float = 0.5) -> list[tuple[str, str, float]]:
    """Align sentences from RU and EN chapter files."""
    print(f"Loading {ru_file.name}...")
    ru_sentences = load_and_split(ru_file, "ru")

    print(f"Loading {en_file.name}...")
    en_sentences = load_and_split(en_file, "en")

    print(f"  RU: {len(ru_sentences)} sentences")
    print(f"  EN: {len(en_sentences)} sentences")

    if method == "simple":
        return simple_align(ru_sentences, en_sentences)
    elif method == "ratio":
        return ratio_based_align(ru_sentences, en_sentences)
    else:  # embedding
        return embedding_align(ru_sentences, en_sentences, threshold)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Align RU and EN sentences")
    parser.add_argument("--ru-dir", default="txt_source", help="Russian chapters directory")
    parser.add_argument("--en-dir", default="txt_source_en", help="English chapters directory")
    parser.add_argument("--chapter", type=int, help="Specific chapter number (default: all)")
    parser.add_argument("--method", choices=["simple", "ratio"], default="ratio",
                       help="Alignment method")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--sample", type=int, default=10, help="Show N sample pairs")

    args = parser.parse_args()

    ru_dir = Path(args.ru_dir)
    en_dir = Path(args.en_dir)

    if args.chapter:
        chapters = [args.chapter]
    else:
        # Find all chapters
        ru_files = sorted(ru_dir.glob("vonnegut_piano_ch*.txt"))
        chapters = [int(f.stem.split("ch")[-1]) for f in ru_files]

    all_aligned = []

    for ch in chapters:
        ru_file = ru_dir / f"vonnegut_piano_ch{ch:02d}.txt"
        en_file = en_dir / f"vonnegut_piano_en_ch{ch:02d}.txt"

        if not ru_file.exists():
            print(f"Warning: {ru_file} not found")
            continue
        if not en_file.exists():
            print(f"Warning: {en_file} not found")
            continue

        print(f"\n=== Chapter {ch} ===")
        aligned = align_chapter(ru_file, en_file, args.method)

        # Stats
        matched = sum(1 for ru, en in aligned if ru and en)
        print(f"  Aligned: {matched}/{len(aligned)} ({100*matched/len(aligned):.1f}%)")

        all_aligned.extend([(ch, ru, en) for ru, en in aligned])

    # Show samples
    if args.sample > 0:
        print(f"\n=== Sample aligned pairs ===")
        import random
        matched_pairs = [(ch, ru, en) for ch, ru, en in all_aligned if ru and en]
        samples = random.sample(matched_pairs, min(args.sample, len(matched_pairs)))

        for ch, ru, en in samples:
            print(f"\n[Ch{ch}]")
            print(f"  RU: {ru[:100]}{'...' if len(ru) > 100 else ''}")
            print(f"  EN: {en[:100]}{'...' if len(en) > 100 else ''}")

    # Save output
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("chapter\tru\ten\n")
            for ch, ru, en in all_aligned:
                # Escape tabs and newlines
                ru_clean = ru.replace('\t', ' ').replace('\n', ' ')
                en_clean = en.replace('\t', ' ').replace('\n', ' ')
                f.write(f"{ch}\t{ru_clean}\t{en_clean}\n")
        print(f"\nSaved {len(all_aligned)} pairs to {output_path}")

    # Summary
    total = len(all_aligned)
    matched = sum(1 for _, ru, en in all_aligned if ru and en)
    print(f"\n=== Summary ===")
    print(f"Total pairs: {total}")
    print(f"Matched: {matched} ({100*matched/total:.1f}%)")
    print(f"RU only: {sum(1 for _, ru, en in all_aligned if ru and not en)}")
    print(f"EN only: {sum(1 for _, ru, en in all_aligned if not ru and en)}")


if __name__ == "__main__":
    main()
