"""Text splitting module for sentence tokenization."""

import re
from typing import Optional

try:
    import ssl
    import certifi
    # Fix SSL certificate verification for NLTK downloads
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass

try:
    import nltk
    from nltk.tokenize import sent_tokenize

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


from core.languages import (
    RUSSIAN, ENGLISH, SPANISH, SPANISH_LATAM, GERMAN, FRENCH, PORTUGUESE_BR,
    require_language, get_language
)

# NLTK language mapping (uses language constants)
NLTK_LANG_MAP = {
    RUSSIAN.code: "russian",
    ENGLISH.code: "english",
    SPANISH.code: "spanish",
    SPANISH_LATAM.code: "spanish",  # NLTK doesn't distinguish variants
    GERMAN.code: "german",
    FRENCH.code: "french",
    PORTUGUESE_BR.code: "portuguese",
}

# Abbreviations that should NOT end sentences (per language)
ABBREVIATIONS = {
    ENGLISH.code: [
        "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Jr.", "Sr.", "vs.", "etc.",
        "i.e.", "e.g.", "Inc.", "Ltd.", "Co.", "Corp.", "Ave.", "St.", "Rd.",
        "Mt.", "ft.", "oz.", "lb.", "Jan.", "Feb.", "Mar.", "Apr.", "Jun.",
        "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.", "Rev.", "Gen.", "Col.",
        "Lt.", "Sgt.", "Capt.", "Cmdr.", "Adm.", "Ph.D.", "M.D.", "B.A.", "M.A.",
    ],
    RUSSIAN.code: [
        "г.", "гг.", "т.д.", "т.п.", "т.е.", "др.", "пр.", "ул.", "д.", "кв.",
        "им.", "проф.", "доц.", "канд.", "акад.", "чл.", "корр.", "ред.", "изд.",
        "см.", "ср.", "напр.", "п.", "пп.", "ч.", "с.", "стр.", "рис.", "табл.",
        "млн.", "млрд.", "тыс.", "руб.", "коп.", "м.", "км.", "кг.", "гр.",
    ],
    SPANISH.code: [
        "Sr.", "Sra.", "Srta.", "Dr.", "Dra.", "Prof.", "Ud.", "Uds.", "etc.",
        "Lic.", "Ing.", "Arq.", "Abog.", "Mtro.", "Mtra.", "Pbro.", "Mons.",
        "Gral.", "Cnel.", "Cap.", "Tte.", "Sgt.", "pág.", "págs.", "vol.",
        "núm.", "tel.", "fax.", "aprox.", "máx.", "mín.", "prom.",
    ],
}

# Compiled regex for single-letter initials and acronyms
#
# Pattern 1: Single uppercase letter + period (initials like "А. С. Пушкин" or "J. R. R. Tolkien")
# - Matches any single uppercase letter followed by period
# - Works for both Cyrillic (А-ЯЁ) and Latin (A-Z)
# - Examples: "А.", "B.", "Щ."
#
# Pattern 2: Acronyms like "Щ.И.Т." or "S.H.I.E.L.D." or "У.С.С.Р."
# - Multiple single letters with periods
# - Matched separately to protect entire acronym
#
SINGLE_LETTER_PATTERN = re.compile(r'(?<![A-ZА-ЯЁa-zа-яё])([A-ZА-ЯЁ])\.(?=\s|$|[^A-ZА-ЯЁa-zа-яё]|[A-ZА-ЯЁ]\.)')

# Acronym pattern: 2+ single letters with dots (Щ.И.Т., S.H.I.E.L.D., etc.)
ACRONYM_PATTERN = re.compile(r'\b([A-ZА-ЯЁ]\.){2,}')

# Ellipsis pattern: 3+ dots (... or …)
# Should not split sentence in the middle of ellipsis
ELLIPSIS_PATTERN = re.compile(r'\.{2,}|…')

# Numbers with dots (decimals, versions, times): 3.14, 2.0, 10.30
# Pattern: digit + dot + digit
DECIMAL_PATTERN = re.compile(r'(\d+)\.(\d+)')

# URLs and domains: google.com, example.org
# Pattern: word + dot + common TLD or word
DOMAIN_PATTERN = re.compile(r'(\w+)\.(com|org|net|ru|io|dev|co|edu|gov|info|me|tv|uk|de|fr|es|it|nl|pl|ua|by|kz)\b', re.IGNORECASE)

# Numbered list items: "1.", "2.", "10." at start of text or after whitespace
# Don't split sentence after list number
NUMBERED_LIST_PATTERN = re.compile(r'(?:^|\s)(\d{1,3})\.')

# Common file extensions that shouldn't cause splits
FILE_EXT_PATTERN = re.compile(r'(\w+)\.(json|xml|txt|md|py|js|ts|html|css|yml|yaml|csv|pdf|doc|docx|xls|xlsx|mp3|mp4|wav|jpg|png|gif|zip|tar|gz)\b', re.IGNORECASE)

# Legacy pattern for backwards compatibility
INITIAL_PATTERN = SINGLE_LETTER_PATTERN


# Default max sentence length for bilingual audiobooks
# Longer sentences are hard to follow with subtitles
DEFAULT_MAX_SENTENCE_LENGTH = 95  # characters


class TextSplitter:
    """Splits text into sentences."""

    def __init__(self, language: str = ENGLISH.code, max_sentence_length: int = DEFAULT_MAX_SENTENCE_LENGTH):
        """
        Initialize splitter.

        Args:
            language: Language code (ru, en, es, es-latam, etc.)
            max_sentence_length: Maximum sentence length before splitting on punctuation
                                 Set to 0 or None to disable

        Raises:
            UnsupportedLanguageError: If language is not supported
        """
        from core.languages import UnsupportedLanguageError

        # Validate and normalize language code
        lang = get_language(language)
        if lang is None:
            raise UnsupportedLanguageError(language, "TextSplitter")

        self.language = lang.code
        self.max_sentence_length = max_sentence_length or 0

        # Get abbreviations - use base code for Spanish variants
        base_code = lang.code.split("-")[0]  # es-latam -> es
        self.abbreviations = ABBREVIATIONS.get(lang.code, ABBREVIATIONS.get(base_code, []))
        self._ensure_nltk_data()

        # Pre-compile abbreviation patterns for this language
        self._abbr_patterns = []
        for abbr in self.abbreviations:
            # Escape special chars and create pattern
            escaped = re.escape(abbr)
            self._abbr_patterns.append((abbr, f"_ABBR_{abbr.replace('.', '_DOT_')}_"))

    def _ensure_nltk_data(self) -> None:
        """Download required NLTK data if not present."""
        if not NLTK_AVAILABLE:
            return

        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            print("Downloading NLTK punkt tokenizer...")
            nltk.download("punkt_tab", quiet=True)

    def split(self, text: str) -> list[str]:
        """
        Split text into sentences.

        Args:
            text: Input text to split

        Returns:
            List of sentences
        """
        if not text:
            return []

        # First, split by dialogue markers (new line + em-dash)
        # This handles Russian dialogue format where each "— " starts new speech
        paragraphs = self._split_dialogues(text)

        all_sentences = []
        for para in paragraphs:
            # Clean paragraph
            para = self._clean_text(para)
            if not para:
                continue

            # Try NLTK first
            if NLTK_AVAILABLE:
                sentences = self._split_nltk(para)
            else:
                sentences = self._split_regex(para)

            all_sentences.extend(sentences)

        # Post-process: strip and filter empty
        result = [s.strip() for s in all_sentences if s.strip()]

        # Split long sentences if max_sentence_length is set
        if self.max_sentence_length > 0:
            result = self._split_long_sentences(result)

        return result

    def _split_long_sentences(self, sentences: list[str]) -> list[str]:
        """
        Split sentences that exceed max_sentence_length.

        Tries to split on (in order of preference):
        1. Semicolon (;)
        2. Em-dash with spaces ( — )
        3. Comma followed by conjunction (, и, , а, , но, , or, , and, , but)
        4. Any comma near the middle
        """
        result = []

        for sentence in sentences:
            if len(sentence) <= self.max_sentence_length:
                result.append(sentence)
                continue

            # Try to split
            parts = self._split_long_sentence(sentence)
            result.extend(parts)

        return result

    def _split_long_sentence(self, sentence: str, depth: int = 0) -> list[str]:
        """Split a single long sentence into smaller parts."""
        if len(sentence) <= self.max_sentence_length:
            return [sentence]

        # Prevent infinite recursion
        if depth > 10:
            return [sentence]

        # 1. Try semicolon first (strongest break point)
        if ';' in sentence:
            parts = sentence.split(';')
            if len(parts) > 1:
                # Add semicolon back to all but last part
                parts = [p.strip() + ';' for p in parts[:-1]] + [parts[-1].strip()]
                parts = [p for p in parts if p.strip() and p != ';']
                if parts:
                    # Recursively split if still too long
                    return self._flatten_split([self._split_long_sentence(p, depth + 1) for p in parts])

        # 2. Try em-dash with spaces ( — )
        if ' — ' in sentence:
            parts = sentence.split(' — ')
            if len(parts) > 1:
                # Keep em-dash at start of continuation
                parts = [parts[0].strip()] + ['— ' + p.strip() for p in parts[1:]]
                parts = [p for p in parts if p.strip() and p != '—']
                if parts:
                    return self._flatten_split([self._split_long_sentence(p, depth + 1) for p in parts])

        # 3. Try comma + conjunction (best for natural splits)
        conj_patterns = [
            ', и ', ', а ', ', но ', ', однако ', ', хотя ',  # Russian
            ', or ', ', and ', ', but ', ', yet ', ', so ',    # English
            ', y ', ', o ', ', pero ', ', aunque ',            # Spanish
        ]
        for pattern in conj_patterns:
            if pattern in sentence:
                idx = sentence.find(pattern)
                # Split after comma, before conjunction
                part1 = sentence[:idx + 1].strip()  # includes comma
                part2 = sentence[idx + 2:].strip()  # starts with conjunction
                if part1 and part2:
                    return self._flatten_split([
                        self._split_long_sentence(part1, depth + 1),
                        self._split_long_sentence(part2, depth + 1)
                    ])

        # 4. Try any comma near the middle (last resort)
        if ',' in sentence:
            mid = len(sentence) // 2
            # Find comma closest to middle
            commas = [i for i, c in enumerate(sentence) if c == ',']
            if commas:
                best_comma = min(commas, key=lambda x: abs(x - mid))
                # Only split if comma is not too close to edges (at least 20% from each side)
                if len(sentence) * 0.2 < best_comma < len(sentence) * 0.8:
                    part1 = sentence[:best_comma + 1].strip()
                    part2 = sentence[best_comma + 1:].strip()
                    if part1 and part2:
                        return self._flatten_split([
                            self._split_long_sentence(part1, depth + 1),
                            self._split_long_sentence(part2, depth + 1)
                        ])

        # Can't split further - return as is
        return [sentence]

    def _flatten_split(self, nested: list[list[str]]) -> list[str]:
        """Flatten nested list of sentence parts."""
        result = []
        for parts in nested:
            result.extend(parts)
        return result

    def _protect_abbreviations(self, text: str) -> str:
        """Replace abbreviations with placeholders to prevent sentence splitting."""
        protected = text

        # 1. Protect ellipsis first (... or …) - most important
        # Replace with placeholder to prevent splitting
        protected = ELLIPSIS_PATTERN.sub('_ELLIPSIS_', protected)

        # 2. Protect file extensions (config.json, data.csv)
        def protect_file_ext(match):
            return match.group(1) + '_FEXT_' + match.group(2)
        protected = FILE_EXT_PATTERN.sub(protect_file_ext, protected)

        # 3. Protect domains/URLs (google.com, example.org)
        def protect_domain(match):
            return match.group(1) + '_DOM_' + match.group(2)
        protected = DOMAIN_PATTERN.sub(protect_domain, protected)

        # 4. Protect decimal numbers (3.14, 10.30, 2.0)
        protected = DECIMAL_PATTERN.sub(r'\1_DECIMAL_\2', protected)

        # 5. Protect numbered list items (1. First, 2. Second)
        def protect_numbered(match):
            prefix = match.group(0)[:-len(match.group(1)) - 1]  # space or start
            return prefix + match.group(1) + '_NUM_'
        protected = NUMBERED_LIST_PATTERN.sub(protect_numbered, protected)

        # 6. Protect acronyms (Щ.И.Т., S.H.I.E.L.D., У.С.С.Р.)
        # These are sequences of single uppercase letters with dots
        def protect_acronym(match):
            acronym = match.group(0)
            return acronym.replace('.', '_ACRO_')
        protected = ACRONYM_PATTERN.sub(protect_acronym, protected)

        # 5. Protect single-letter initials (A. B. Smith, А. С. Пушкин)
        # Any single uppercase letter followed by period
        protected = SINGLE_LETTER_PATTERN.sub(r'\1_INIT_', protected)

        # 6. Protect known abbreviations (т.д., etc., Dr., etc.)
        for abbr, placeholder in self._abbr_patterns:
            protected = protected.replace(abbr, placeholder)

        return protected

    def _restore_abbreviations(self, text: str) -> str:
        """Restore abbreviations from placeholders."""
        restored = text

        # IMPORTANT: Restore in reverse order of protection!
        # Known abbreviations first (they contain _DOT_ in placeholder)
        for abbr, placeholder in self._abbr_patterns:
            restored = restored.replace(placeholder, abbr)

        # Restore initials (A_INIT_ -> A.)
        restored = restored.replace('_INIT_', '.')

        # Restore acronyms (Щ_ACRO_И_ACRO_Т_ACRO_ -> Щ.И.Т.)
        restored = restored.replace('_ACRO_', '.')

        # Restore numbered list items (1_NUM_ -> 1.)
        restored = restored.replace('_NUM_', '.')

        # Restore decimal numbers (3_DECIMAL_14 -> 3.14)
        restored = restored.replace('_DECIMAL_', '.')

        # Restore domains (google_DOM_com -> google.com)
        restored = restored.replace('_DOM_', '.')

        # Restore file extensions (config_FEXT_json -> config.json)
        restored = restored.replace('_FEXT_', '.')

        # Restore ellipsis (_ELLIPSIS_ -> ...)
        restored = restored.replace('_ELLIPSIS_', '...')

        return restored

    def _split_dialogues(self, text: str) -> list[str]:
        """Split text by dialogue markers (newline + em-dash or hyphen)."""
        # Split on newline followed by em-dash "—" or hyphen "-" (dialogue start)
        # Pattern: newline + optional whitespace + em-dash/hyphen
        # Improved pattern: handles both "—" (em-dash) and "- " (hyphen-space)
        parts = re.split(r'\n\s*(?=[—–-]\s)', text)

        result = []
        for part in parts:
            # Also split on double newlines (paragraphs)
            subparts = re.split(r'\n\s*\n', part)
            result.extend(subparts)

        return [p.strip() for p in result if p.strip()]

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def _split_nltk(self, text: str) -> list[str]:
        """Split using NLTK sent_tokenize."""
        nltk_lang = NLTK_LANG_MAP.get(self.language, "english")

        # Protect abbreviations and initials before splitting
        protected = self._protect_abbreviations(text)

        try:
            sentences = sent_tokenize(protected, language=nltk_lang)
            # Restore abbreviations in results
            return [self._restore_abbreviations(s) for s in sentences]
        except Exception:
            # Fallback to regex if NLTK fails
            return self._split_regex(text)

    def _split_regex(self, text: str) -> list[str]:
        """
        Fallback regex-based sentence splitting.

        Handles:
        - Standard punctuation (. ! ?)
        - Ellipsis
        - Russian and English text
        - Abbreviations and initials
        """
        # Protect abbreviations and initials
        protected = self._protect_abbreviations(text)

        # Split on sentence boundaries
        # Match: period/exclamation/question + space(s) + capital letter (Latin or Cyrillic)
        parts = re.split(r'([.!?]+)\s+(?=[A-ZА-ЯЁ])', protected)

        # Recombine parts (punctuation gets separated by split with capture group)
        sentences = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and re.match(r'^[.!?]+$', parts[i + 1] if i + 1 < len(parts) else ''):
                sentences.append(parts[i] + parts[i + 1])
                i += 2
            else:
                if parts[i].strip():
                    sentences.append(parts[i])
                i += 1

        # Restore abbreviations in results
        return [self._restore_abbreviations(s) for s in sentences]


def split_text(
    text: str,
    language: str = ENGLISH.code,
    max_sentence_length: int = DEFAULT_MAX_SENTENCE_LENGTH,
) -> list[str]:
    """
    Convenience function to split text into sentences.

    Args:
        text: Input text
        language: Language code
        max_sentence_length: Maximum sentence length before splitting (0 to disable)

    Returns:
        List of sentences

    Raises:
        UnsupportedLanguageError: If language is not supported
    """
    splitter = TextSplitter(language, max_sentence_length=max_sentence_length)
    return splitter.split(text)
