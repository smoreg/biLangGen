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


# NLTK language mapping
NLTK_LANG_MAP = {
    "ru": "russian",
    "en": "english",
    "es": "spanish",
}

# Abbreviations that should NOT end sentences (per language)
ABBREVIATIONS = {
    "en": [
        "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Jr.", "Sr.", "vs.", "etc.",
        "i.e.", "e.g.", "Inc.", "Ltd.", "Co.", "Corp.", "Ave.", "St.", "Rd.",
        "Mt.", "ft.", "oz.", "lb.", "Jan.", "Feb.", "Mar.", "Apr.", "Jun.",
        "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.", "Rev.", "Gen.", "Col.",
        "Lt.", "Sgt.", "Capt.", "Cmdr.", "Adm.", "Ph.D.", "M.D.", "B.A.", "M.A.",
    ],
    "ru": [
        "г.", "гг.", "т.д.", "т.п.", "т.е.", "др.", "пр.", "ул.", "д.", "кв.",
        "им.", "проф.", "доц.", "канд.", "акад.", "чл.", "корр.", "ред.", "изд.",
        "см.", "ср.", "напр.", "п.", "пп.", "ч.", "с.", "стр.", "рис.", "табл.",
        "млн.", "млрд.", "тыс.", "руб.", "коп.", "м.", "км.", "кг.", "гр.",
    ],
    "es": [
        "Sr.", "Sra.", "Srta.", "Dr.", "Dra.", "Prof.", "Ud.", "Uds.", "etc.",
        "Lic.", "Ing.", "Arq.", "Abog.", "Mtro.", "Mtra.", "Pbro.", "Mons.",
        "Gral.", "Cnel.", "Cap.", "Tte.", "Sgt.", "pág.", "págs.", "vol.",
        "núm.", "tel.", "fax.", "aprox.", "máx.", "mín.", "prom.",
    ],
}

# Compiled regex for single-letter initials (A. B. C.)
# Matches: SINGLE uppercase letter (not preceded by another letter) followed by period
# Does NOT match words like "Ул." or "Dr." - those are abbreviations
# Only matches patterns like "A. " or "А. " where the letter stands alone
INITIAL_PATTERN = re.compile(r'(?<![A-ZА-ЯЁa-zа-яё])([A-ZА-ЯЁ])\.(\s*)(?=[A-ZА-ЯЁa-zа-яё])')


class TextSplitter:
    """Splits text into sentences."""

    def __init__(self, language: str = "en"):
        """
        Initialize splitter.

        Args:
            language: Language code (ru, en, es)
        """
        self.language = language
        self.abbreviations = ABBREVIATIONS.get(language, [])
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

        # Post-process
        return [s.strip() for s in all_sentences if s.strip()]

    def _protect_abbreviations(self, text: str) -> str:
        """Replace abbreviations with placeholders to prevent sentence splitting."""
        protected = text

        # Protect single-letter initials first (A. B. Smith, А. С. Пушкин)
        # Replace "A. " with "A_INIT_ " to preserve spacing
        # \1 = letter, \2 = space (if any)
        protected = INITIAL_PATTERN.sub(r'\1_INIT_\2', protected)

        # Protect known abbreviations
        for abbr, placeholder in self._abbr_patterns:
            protected = protected.replace(abbr, placeholder)

        return protected

    def _restore_abbreviations(self, text: str) -> str:
        """Restore abbreviations from placeholders."""
        restored = text

        # Restore initials
        restored = restored.replace('_INIT_', '.')

        # Restore abbreviations
        for abbr, placeholder in self._abbr_patterns:
            restored = restored.replace(placeholder, abbr)

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


def split_text(text: str, language: str = "en") -> list[str]:
    """
    Convenience function to split text into sentences.

    Args:
        text: Input text
        language: Language code

    Returns:
        List of sentences
    """
    splitter = TextSplitter(language)
    return splitter.split(text)
