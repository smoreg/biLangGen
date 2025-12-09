#!/usr/bin/env python3
"""Split book by Roman numeral chapters (I, II, III, etc.)"""

import re
import sys
from pathlib import Path

def roman_to_int(s: str) -> int:
    """Convert Roman numeral to integer."""
    # Normalize Cyrillic Х to Latin X
    s = s.replace('Х', 'X').replace('х', 'X')
    roman_values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    result = 0
    prev = 0
    for char in reversed(s.upper()):
        val = roman_values.get(char, 0)
        if val < prev:
            result -= val
        else:
            result += val
        prev = val
    return result

def split_by_chapters(input_file: Path, output_dir: Path, prefix: str = "vonnegut_piano"):
    """Split file by Roman numeral chapter markers."""

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Pattern: line contains only Roman numerals (Latin or Cyrillic X/Х)
    # Note: Some texts use Cyrillic Х instead of Latin X
    chapter_pattern = re.compile(r'^([IVXLCХХ]+)\s*$', re.IGNORECASE)

    chapters = []
    current_chapter = None
    current_lines = []

    for i, line in enumerate(lines):
        match = chapter_pattern.match(line.strip())
        if match:
            # Save previous chapter
            if current_chapter is not None:
                chapters.append((current_chapter, current_lines))

            current_chapter = match.group(1)
            current_lines = []
        elif current_chapter is not None:
            current_lines.append(line)

    # Don't forget last chapter
    if current_chapter is not None:
        chapters.append((current_chapter, current_lines))

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write chapters
    for roman, content in chapters:
        num = roman_to_int(roman)
        filename = f"{prefix}_ch{num:02d}.txt"
        filepath = output_dir / filename

        # Clean up content - remove leading/trailing empty lines
        text = ''.join(content).strip()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)

        print(f"  {filename}: {len(text):,} chars, chapter {roman}")

    print(f"\nTotal: {len(chapters)} chapters saved to {output_dir}")
    return chapters

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_chapters.py <input_file> [output_dir] [prefix]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("txt_source")
    prefix = sys.argv[3] if len(sys.argv) > 3 else input_file.stem.lower()

    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)

    split_by_chapters(input_file, output_dir, prefix)
