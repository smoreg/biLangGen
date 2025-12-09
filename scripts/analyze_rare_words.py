#!/usr/bin/env python3
"""
Analyze rare words from existing project and export to JSON.

This script:
1. Loads an existing project with translations
2. Extracts rare words from target sentences
3. Filters cognates (words that sound similar in both languages)
4. Outputs structured JSON for analysis

Usage:
    python scripts/analyze_rare_words.py PROJECT_NAME
    python scripts/analyze_rare_words.py Страж-птица_ru_es
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from project import ProjectManager


def transliterate_cyrillic(text: str) -> str:
    """Transliterate Cyrillic to Latin for comparison."""
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        # Also handle common Latin letter equivalents
        'tion': 'ция', 'sion': 'сия',
    }
    result = text.lower()
    for cyr, lat in mapping.items():
        result = result.replace(cyr, lat)
    return result


def normalize_for_comparison(text: str) -> str:
    """Normalize word for cognate comparison."""
    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # Lowercase
    text = text.lower()
    # Remove common suffixes that differ between languages
    suffixes = ['ción', 'sión', 'tion', 'sion', 'ция', 'сия', 'ный', 'ая', 'ое', 'ий']
    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[:-len(suffix)]
            break
    return text


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def is_proper_noun(word_target: str, word_source: str, threshold: float = 0.25) -> bool:
    """
    Check if word is a proper noun by comparing target and source.

    Proper nouns (names, places) are transliterated, not translated:
    - "Massachusetts" → "Массачусетс" (same word, different script)
    - "Alicia" → "Алиса" (same name)
    - "revólver" → "револьвер" (NOT proper noun, just cognate)

    Uses stricter threshold than cognate detection (0.25 vs 0.4).
    Also checks if BOTH words start with capital letter.

    Args:
        word_target: Word in target language (Spanish)
        word_source: Translation in source language (Russian)
        threshold: Max edit distance ratio (0.25 = very similar)

    Returns:
        True if likely a proper noun (transliterated name/place)
    """
    if not word_target or not word_source:
        return False

    # Both should start with capital letter for proper noun
    # (but in DB we might have lowercase, so also check similarity)
    both_capitalized = word_target[0].isupper() and word_source[0].isupper()

    # Normalize and transliterate
    target_norm = normalize_for_comparison(word_target)
    source_translit = transliterate_cyrillic(word_source)
    source_norm = normalize_for_comparison(source_translit)

    # If very short, require exact match
    min_len = min(len(target_norm), len(source_norm))
    if min_len < 3:
        return target_norm == source_norm and both_capitalized

    # Calculate similarity
    distance = levenshtein_distance(target_norm, source_norm)
    max_len = max(len(target_norm), len(source_norm))
    ratio = distance / max_len

    # Proper noun: very similar AND both capitalized
    # OR extremely similar (ratio < 0.15) regardless of capitalization
    if ratio <= 0.15:
        return True  # Very close match = definitely proper noun
    if ratio <= threshold and both_capitalized:
        return True  # Close match + both caps = likely proper noun

    return False


def is_cognate(word_target: str, word_source: str, threshold: float = 0.4) -> bool:
    """
    Check if two words are cognates (sound similar).

    Uses transliteration + Levenshtein distance.
    threshold: max ratio of edits to word length (0.4 = 40% different allowed)
    """
    # Transliterate Cyrillic to Latin
    target_norm = normalize_for_comparison(word_target)
    source_translit = transliterate_cyrillic(word_source)
    source_norm = normalize_for_comparison(source_translit)

    # If either is too short, be more strict
    min_len = min(len(target_norm), len(source_norm))
    if min_len < 3:
        return target_norm == source_norm

    # Calculate distance
    distance = levenshtein_distance(target_norm, source_norm)
    max_len = max(len(target_norm), len(source_norm))

    # Ratio of differences
    ratio = distance / max_len

    return ratio <= threshold


def analyze_project(project_name: str, output_path: str = None, max_per_sentence: int = 5):
    """Analyze rare words in project and export to JSON.

    Reads rare words from database (already extracted and translated by pipeline).
    """
    pm = ProjectManager(Path("projects"))
    project = pm.get_project(project_name)

    if not project:
        print(f"Project not found: {project_name}")
        sys.exit(1)

    # Get all sentences
    source_sentences = project.db.get_sentences(project.meta.source_lang)
    target_sentences = project.db.get_sentences(project.meta.target_lang)

    if not target_sentences:
        print("No target sentences found")
        sys.exit(1)

    print(f"Found {len(source_sentences)} source, {len(target_sentences)} target sentences")

    # Get rare words from database (already extracted by pipeline)
    db_rare_words = project.db.conn.execute(
        'SELECT sentence_idx, word, zipf, translation FROM rare_words ORDER BY sentence_idx, zipf'
    ).fetchall()

    print(f"Loaded {len(db_rare_words)} rare words from database")

    # Group by sentence_idx
    rare_by_sentence = {}
    for row in db_rare_words:
        sentence_idx, word, zipf, translation = row
        if sentence_idx not in rare_by_sentence:
            rare_by_sentence[sentence_idx] = []
        rare_by_sentence[sentence_idx].append({
            "word": word,
            "zipf": zipf,
            "lemma": word,  # DB doesn't store lemma separately
            "translation": translation
        })

    # Build analysis structure
    analysis = {
        "project": project_name,
        "source_lang": project.meta.source_lang,
        "target_lang": project.meta.target_lang,
        "total_sentences": len(target_sentences),
        "max_per_sentence": max_per_sentence,
        "sentences": [],
        "cognates_found": [],
        "proper_nouns_found": [],
        "statistics": {}
    }

    total_words = 0
    total_cognates = 0
    words_per_sentence = []

    # Analyze each sentence
    for i, (src, tgt) in enumerate(zip(source_sentences, target_sentences)):
        rare_words = rare_by_sentence.get(i, [])

        # Check for cognates and proper nouns
        filtered_words = []
        cognates = []
        proper_nouns = []

        for rw in rare_words:
            # Skip words without translation
            if not rw['translation']:
                filtered_words.append(rw)
                continue

            # Check if proper noun (transliterated name - very similar to translation)
            if is_proper_noun(rw['word'], rw['translation']):
                proper_nouns.append({
                    "word": rw['word'],
                    "translation": rw['translation'],
                    "sentence_idx": i
                })
                continue  # Skip proper nouns

            # Check if cognate (similar sounding words)
            if is_cognate(rw['word'], rw['translation']):
                cognates.append({
                    "target": rw['word'],
                    "source": rw['translation'],
                    "sentence_idx": i
                })
                total_cognates += 1
            else:
                filtered_words.append(rw)

        analysis["cognates_found"].extend(cognates)
        analysis["proper_nouns_found"].extend(proper_nouns)

        # Count words in sentence
        src_word_count = len(re.findall(r'\b\w+\b', src['text']))
        tgt_word_count = len(re.findall(r'\b\w+\b', tgt['text']))

        total_words += len(filtered_words)
        words_per_sentence.append(len(filtered_words))

        analysis["sentences"].append({
            "idx": i,
            "source": src['text'],
            "target": tgt['text'],
            "source_word_count": src_word_count,
            "target_word_count": tgt_word_count,
            "rare_words_original": len(rare_words),
            "rare_words_filtered": len(filtered_words),
            "cognates_removed": len(cognates),
            "rare_words": filtered_words
        })

    # Calculate statistics
    avg_words = total_words / len(target_sentences) if target_sentences else 0
    total_proper_nouns = len(analysis["proper_nouns_found"])
    analysis["statistics"] = {
        "total_rare_words": total_words,
        "total_cognates_removed": total_cognates,
        "total_proper_nouns_removed": total_proper_nouns,
        "average_words_per_sentence": round(avg_words, 2),
        "max_words_per_sentence": max(words_per_sentence) if words_per_sentence else 0,
        "min_words_per_sentence": min(words_per_sentence) if words_per_sentence else 0,
        "sentences_with_0_words": words_per_sentence.count(0),
        "sentences_with_5plus_words": sum(1 for w in words_per_sentence if w >= 5),
    }

    # Output
    if output_path is None:
        output_path = f"analysis_{project_name}.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis saved to: {output_path}")
    print(f"\nStatistics:")
    for key, value in analysis["statistics"].items():
        print(f"  {key}: {value}")

    print(f"\nSample cognates found:")
    for cog in analysis["cognates_found"][:10]:
        print(f"  {cog['target']} ~ {cog['source']}")

    print(f"\nSample proper nouns found:")
    for pn in analysis["proper_nouns_found"][:10]:
        print(f"  {pn['word']}")

    return analysis


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_rare_words.py PROJECT_NAME [OUTPUT_PATH]")
        print("\nAvailable projects:")
        pm = ProjectManager(Path("projects"))
        for p in pm.list_projects():
            print(f"  - {p}")
        sys.exit(1)

    project_name = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    analyze_project(project_name, output_path)
