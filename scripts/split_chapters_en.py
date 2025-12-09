#!/usr/bin/env python3
"""Split English Player Piano book into chapters.

Chapters are marked as "Chapter One", "Chapter Two", etc.
"""

import re
import sys
from pathlib import Path


# Word to number mapping (with and without hyphens)
WORD_TO_NUM = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'twenty-one': 21, 'twenty one': 21, 'twenty-two': 22, 'twenty two': 22,
    'twenty-three': 23, 'twenty three': 23, 'twenty-four': 24, 'twenty four': 24,
    'twenty-five': 25, 'twenty five': 25, 'twenty-six': 26, 'twenty six': 26,
    'twenty-seven': 27, 'twenty seven': 27, 'twenty-eight': 28, 'twenty eight': 28,
    'twenty-nine': 29, 'twenty nine': 29, 'thirty': 30,
    'thirty-one': 31, 'thirty one': 31, 'thirty-two': 32, 'thirty two': 32,
    'thirty-three': 33, 'thirty three': 33, 'thirty-four': 34, 'thirty four': 34,
    'thirty-five': 35, 'thirty five': 35,
}


def word_to_int(word: str) -> int:
    """Convert English word number to integer."""
    return WORD_TO_NUM.get(word.lower(), 0)


def split_book_into_chapters(text: str, output_dir: Path, base_name: str = "vonnegut_piano_en"):
    """Split book into chapters based on 'Chapter X' markers."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pattern: "Chapter One", "Chapter Two", "Chapter Twenty One" (with or without hyphen)
    # Match at start of line or after newlines
    chapter_pattern = re.compile(
        r'^Chapter\s+(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|'
        r'Eleven|Twelve|Thirteen|Fourteen|Fifteen|Sixteen|Seventeen|Eighteen|'
        r'Nineteen|Twenty|Twenty[- ]One|Twenty[- ]Two|Twenty[- ]Three|Twenty[- ]Four|'
        r'Twenty[- ]Five|Twenty[- ]Six|Twenty[- ]Seven|Twenty[- ]Eight|Twenty[- ]Nine|'
        r'Thirty|Thirty[- ]One|Thirty[- ]Two|Thirty[- ]Three|Thirty[- ]Four|Thirty[- ]Five)\s*$',
        re.MULTILINE | re.IGNORECASE
    )

    # Find all chapter markers
    matches = list(chapter_pattern.finditer(text))

    if not matches:
        print("No chapters found!")
        return []

    print(f"Found {len(matches)} chapters")

    chapters = []
    for i, match in enumerate(matches):
        chapter_word = match.group(1)
        chapter_num = word_to_int(chapter_word)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        # Extract chapter content (skip the chapter marker itself)
        content = text[start:end].strip()

        # Clean up: remove excessive newlines
        content = re.sub(r'\n{3,}', '\n\n', content)

        chapters.append({
            'num': chapter_num,
            'word': chapter_word,
            'content': content
        })

    # Save chapters
    saved = []
    for ch in chapters:
        filename = f"{base_name}_ch{ch['num']:02d}.txt"
        filepath = output_dir / filename
        filepath.write_text(ch['content'], encoding='utf-8')
        saved.append(filepath)
        print(f"  Chapter {ch['num']:2d} ({ch['word']:>12s}): {len(ch['content']):6d} chars -> {filename}")

    return saved


def main():
    if len(sys.argv) < 2:
        print("Usage: python split_chapters_en.py <book.txt> [output_dir]")
        print("  Encoding: CP1251 (Windows Cyrillic) will be auto-detected")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("txt_source_en")

    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    # Read with CP1251 encoding (common for Russian downloads of English texts)
    with open(input_path, 'rb') as f:
        raw = f.read()

    # Try to decode
    for encoding in ['utf-8', 'cp1251', 'iso-8859-1']:
        try:
            text = raw.decode(encoding)
            print(f"Decoded with {encoding}")
            break
        except UnicodeDecodeError:
            continue
    else:
        print("Failed to decode file")
        sys.exit(1)

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    chapters = split_book_into_chapters(text, output_dir)
    print(f"\nSaved {len(chapters)} chapters to {output_dir}")


if __name__ == "__main__":
    main()
