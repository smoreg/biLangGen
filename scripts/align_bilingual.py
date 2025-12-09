#!/usr/bin/env python3
"""Align Russian and English sentences using Argos Translate.

Uses bidirectional translation (RU→EN and EN→RU) with Jaccard similarity
to match sentences. Handles 1:1, 1:2 (EN merge), and 2:1 (RU merge) cases.

Requirements:
    pip install argostranslate

Usage:
    python scripts/align_bilingual.py --ru txt_source/book_ch01.txt --en txt_source_en/book_en_ch01.txt
    python scripts/align_bilingual.py --ru txt_source/book_ch01.txt --en txt_source_en/book_en_ch01.txt -o aligned.json
"""

import sys
import json
import re
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.text_splitter import TextSplitter

# Stop words for filtering
EN_STOP = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
           'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
           'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
           'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
           'from', 'as', 'into', 'through', 'during', 'before', 'after',
           'above', 'below', 'between', 'under', 'and', 'but', 'or', 'nor',
           'so', 'yet', 'both', 'either', 'neither', 'not', 'only', 'own',
           'same', 'than', 'too', 'very', 'just', 'also', 'now', 'here',
           'there', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
           'any', 'some', 'no', 'such', 'that', 'this', 'these', 'those',
           'what', 'which', 'who', 'whom', 'whose', 'it', 'its', 'he', 'she',
           'him', 'her', 'his', 'hers', 'they', 'them', 'their', 'theirs',
           'i', 'me', 'my', 'mine', 'we', 'us', 'our', 'ours', 'you', 'your',
           'yours'}

RU_STOP = {'и', 'в', 'на', 'с', 'по', 'для', 'к', 'о', 'об', 'от', 'до', 'за',
           'из', 'у', 'при', 'через', 'над', 'под', 'между', 'перед', 'после',
           'а', 'но', 'или', 'да', 'же', 'ли', 'бы', 'не', 'ни', 'то', 'это',
           'что', 'как', 'так', 'когда', 'где', 'куда', 'откуда', 'почему',
           'зачем', 'который', 'какой', 'чей', 'кто', 'я', 'ты', 'он', 'она',
           'оно', 'мы', 'вы', 'они', 'его', 'её', 'их', 'мой', 'твой', 'наш',
           'ваш', 'свой', 'себя', 'сам', 'весь', 'все', 'всё', 'каждый',
           'любой', 'другой', 'такой', 'сам', 'самый', 'один', 'был', 'была',
           'было', 'были', 'быть', 'есть', 'будет', 'будут', 'уже', 'ещё',
           'еще', 'очень', 'только', 'также', 'тоже', 'можно', 'нужно',
           'надо', 'без', 'более', 'менее', 'чем'}


def get_en_words(text: str) -> set[str]:
    """Extract significant English words."""
    words = set(re.findall(r'[a-zA-Z]+', text.lower()))
    return words - EN_STOP


def get_ru_words(text: str) -> set[str]:
    """Extract significant Russian words."""
    words = set(re.findall(r'[а-яёА-ЯЁ]+', text.lower()))
    return words - RU_STOP


def jaccard(set1: set, set2: set) -> float:
    """Jaccard similarity coefficient."""
    if not set1 or not set2:
        return 0.0
    inter = len(set1 & set2)
    union = len(set1 | set2)
    return inter / union if union > 0 else 0.0


class BilingualAligner:
    """Aligns Russian and English sentences using bidirectional translation."""

    def __init__(self, parallel_workers: int = 8):
        self.workers = parallel_workers
        self.ru_to_en = None
        self.en_to_ru = None
        self._init_translators()

    def _init_translators(self):
        """Initialize Argos translators."""
        try:
            import argostranslate.translate
        except ImportError:
            print("ERROR: argostranslate not installed!")
            print("Install with: pip install argostranslate")
            sys.exit(1)

        installed = argostranslate.translate.get_installed_languages()
        ru_lang = next((l for l in installed if l.code == 'ru'), None)
        en_lang = next((l for l in installed if l.code == 'en'), None)

        if not ru_lang or not en_lang:
            print("ERROR: RU-EN language pack not installed!")
            print("Install with:")
            print("  import argostranslate.package")
            print("  argostranslate.package.update_package_index()")
            print("  # Then download and install ru-en and en-ru packages")
            sys.exit(1)

        self.ru_to_en = ru_lang.get_translation(en_lang)
        self.en_to_ru = en_lang.get_translation(ru_lang)

    def translate_batch(self, texts: list[str], direction: str = 'ru_en') -> list[str]:
        """Translate texts in parallel."""
        translator = self.ru_to_en if direction == 'ru_en' else self.en_to_ru
        results = [None] * len(texts)
        done = [0]

        def translate(args):
            idx, text = args
            result = translator.translate(text)
            done[0] += 1
            if done[0] % 50 == 0:
                print(f"  Translated {done[0]}/{len(texts)}...", flush=True)
            return idx, result

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(translate, (i, t)) for i, t in enumerate(texts)]
            for f in as_completed(futures):
                idx, result = f.result()
                results[idx] = result

        return results

    def align(self, ru_sentences: list[str], en_sentences: list[str],
              threshold: float = 0.15, look_ahead: int = 5) -> list[dict]:
        """
        Align Russian and English sentences.

        Returns list of alignment records:
        {
            'ru_idx': [indices],
            'en_idx': [indices],
            'ru_text': [texts],
            'en_text': [texts],
            'score': float,
            'type': '1:1' | '1:2' | '2:1' | 'ru_only' | 'en_only'
        }
        """
        print(f"Sentences: RU={len(ru_sentences)}, EN={len(en_sentences)}")

        # Translate all sentences
        print("Translating RU→EN...")
        ru_as_en = self.translate_batch(ru_sentences, 'ru_en')

        print("Translating EN→RU...")
        en_as_ru = self.translate_batch(en_sentences, 'en_ru')

        print("Aligning...")

        def score_match(ri, ei):
            """Bidirectional match score."""
            ru_trans = get_en_words(ru_as_en[ri])
            en_orig = get_en_words(en_sentences[ei])
            s1 = jaccard(ru_trans, en_orig)

            en_trans = get_ru_words(en_as_ru[ei])
            ru_orig = get_ru_words(ru_sentences[ri])
            s2 = jaccard(en_trans, ru_orig)

            return (s1 + s2) / 2

        def score_1_to_2(ri, ei1, ei2):
            """1 RU = 2 EN (EN sentences merged in translation)."""
            en_combined = en_sentences[ei1] + " " + en_sentences[ei2]
            ru_trans = get_en_words(ru_as_en[ri])
            en_comb = get_en_words(en_combined)
            s1 = jaccard(ru_trans, en_comb)

            en_t1 = get_ru_words(en_as_ru[ei1])
            en_t2 = get_ru_words(en_as_ru[ei2])
            ru_orig = get_ru_words(ru_sentences[ri])
            s2 = jaccard(en_t1 | en_t2, ru_orig)

            return (s1 + s2) / 2

        def score_2_to_1(ri1, ri2, ei):
            """2 RU = 1 EN (RU sentences merged in translation)."""
            ru_t1 = get_en_words(ru_as_en[ri1])
            ru_t2 = get_en_words(ru_as_en[ri2])
            en_orig = get_en_words(en_sentences[ei])
            s1 = jaccard(ru_t1 | ru_t2, en_orig)

            ru_combined = ru_sentences[ri1] + " " + ru_sentences[ri2]
            en_trans = get_ru_words(en_as_ru[ei])
            ru_comb = get_ru_words(ru_combined)
            s2 = jaccard(en_trans, ru_comb)

            return (s1 + s2) / 2

        aligned = []
        ri = 0
        ei = 0

        while ri < len(ru_sentences):
            if ei >= len(en_sentences):
                aligned.append({
                    'ru_idx': [ri], 'en_idx': [],
                    'ru_text': [ru_sentences[ri]], 'en_text': [],
                    'score': 0, 'type': 'ru_only'
                })
                ri += 1
                continue

            # Try 3 alignment options
            scores = []

            # 1:1
            s11 = score_match(ri, ei)
            scores.append(('1:1', s11, [ri], [ei]))

            # 1:2 (EN merge)
            if ei + 1 < len(en_sentences):
                s12 = score_1_to_2(ri, ei, ei + 1)
                scores.append(('1:2', s12, [ri], [ei, ei + 1]))

            # 2:1 (RU merge)
            if ri + 1 < len(ru_sentences):
                s21 = score_2_to_1(ri, ri + 1, ei)
                scores.append(('2:1', s21, [ri, ri + 1], [ei]))

            scores.sort(key=lambda x: -x[1])
            best_type, best_score, best_ri, best_ei = scores[0]

            # Look ahead if score is low
            if best_score < threshold:
                # Try to find better match in EN
                for look in range(1, look_ahead + 1):
                    if ei + look >= len(en_sentences):
                        break
                    test_score = score_match(ri, ei + look)
                    if test_score > threshold and test_score > best_score:
                        # Skip EN sentences
                        for skip in range(look):
                            aligned.append({
                                'ru_idx': [], 'en_idx': [ei + skip],
                                'ru_text': [], 'en_text': [en_sentences[ei + skip]],
                                'score': 0, 'type': 'en_only'
                            })
                        ei += look
                        best_type, best_score, best_ri, best_ei = '1:1', test_score, [ri], [ei]
                        break
                else:
                    # Try to find better match in RU
                    for look in range(1, look_ahead + 1):
                        if ri + look >= len(ru_sentences):
                            break
                        test_score = score_match(ri + look, ei)
                        if test_score > threshold and test_score > best_score:
                            # Skip RU sentences
                            for skip in range(look):
                                aligned.append({
                                    'ru_idx': [ri + skip], 'en_idx': [],
                                    'ru_text': [ru_sentences[ri + skip]], 'en_text': [],
                                    'score': 0, 'type': 'ru_only'
                                })
                            ri += look
                            best_type, best_score, best_ri, best_ei = '1:1', test_score, [ri], [ei]
                            break

            # Record alignment
            aligned.append({
                'ru_idx': best_ri,
                'en_idx': best_ei,
                'ru_text': [ru_sentences[i] for i in best_ri],
                'en_text': [en_sentences[i] for i in best_ei],
                'score': best_score,
                'type': best_type
            })

            ri = max(best_ri) + 1
            ei = max(best_ei) + 1 if best_ei else ei

        return aligned


def load_and_split(filepath: Path, lang: str) -> list[str]:
    """Load file and split into sentences."""
    text = filepath.read_text(encoding='utf-8')
    splitter = TextSplitter(lang, max_sentence_length=1000000)
    return splitter.split(text)


def print_stats(aligned: list[dict]):
    """Print alignment statistics."""
    total = len(aligned)
    by_type = {}
    for a in aligned:
        t = a['type']
        by_type[t] = by_type.get(t, 0) + 1

    ru_count = sum(len(a['ru_idx']) for a in aligned)
    en_count = sum(len(a['en_idx']) for a in aligned)

    high = sum(1 for a in aligned if a['score'] >= 0.15)
    medium = sum(1 for a in aligned if 0.05 <= a['score'] < 0.15)
    low = sum(1 for a in aligned if a['score'] < 0.05 and a['type'] not in ('ru_only', 'en_only'))

    print(f"\n=== Alignment Statistics ===")
    print(f"Total pairs: {total}")
    print(f"RU sentences: {ru_count}, EN sentences: {en_count}")
    print(f"By type: {by_type}")
    print(f"Quality: HIGH={high}, MEDIUM={medium}, LOW={low}")


def main():
    parser = argparse.ArgumentParser(description="Align RU and EN sentences")
    parser.add_argument("--ru", required=True, help="Russian text file")
    parser.add_argument("--en", required=True, help="English text file")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("--threshold", type=float, default=0.15,
                        help="Minimum score threshold (default: 0.15)")
    parser.add_argument("--look-ahead", type=int, default=5,
                        help="Look-ahead distance for resync (default: 5)")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel translation workers (default: 8)")
    parser.add_argument("--sample", type=int, default=10,
                        help="Show N sample alignments (default: 10)")

    args = parser.parse_args()

    ru_file = Path(args.ru)
    en_file = Path(args.en)

    if not ru_file.exists():
        print(f"ERROR: {ru_file} not found")
        sys.exit(1)
    if not en_file.exists():
        print(f"ERROR: {en_file} not found")
        sys.exit(1)

    print(f"Loading {ru_file.name}...")
    ru_sentences = load_and_split(ru_file, "ru")

    print(f"Loading {en_file.name}...")
    en_sentences = load_and_split(en_file, "en")

    aligner = BilingualAligner(parallel_workers=args.workers)
    aligned = aligner.align(
        ru_sentences, en_sentences,
        threshold=args.threshold,
        look_ahead=args.look_ahead
    )

    print_stats(aligned)

    # Show samples
    if args.sample > 0:
        import random
        good_pairs = [a for a in aligned if a['score'] >= 0.15 and a['type'] == '1:1']
        samples = random.sample(good_pairs, min(args.sample, len(good_pairs)))

        print(f"\n=== Sample Alignments ({len(samples)}) ===")
        for a in samples:
            ru = a['ru_text'][0][:80] + ('...' if len(a['ru_text'][0]) > 80 else '')
            en = a['en_text'][0][:80] + ('...' if len(a['en_text'][0]) > 80 else '')
            print(f"[{a['type']}] score={a['score']:.2f}")
            print(f"  RU: {ru}")
            print(f"  EN: {en}")
            print()

    # Save output
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(aligned, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
