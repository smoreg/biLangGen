"""Text splitting module for sentence tokenization."""

import re
from typing import Optional

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


class TextSplitter:
    """Splits text into sentences."""

    def __init__(self, language: str = "en"):
        """
        Initialize splitter.

        Args:
            language: Language code (ru, en, es)
        """
        self.language = language
        self._ensure_nltk_data()

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
        # Clean text first
        text = self._clean_text(text)

        if not text:
            return []

        # Try NLTK first
        if NLTK_AVAILABLE:
            sentences = self._split_nltk(text)
        else:
            sentences = self._split_regex(text)

        # Post-process
        return [s.strip() for s in sentences if s.strip()]

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
        try:
            return sent_tokenize(text, language=nltk_lang)
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
        """
        # Simple approach: split on . ! ? followed by space and capital letter
        # First, protect common abbreviations by replacing them temporarily
        protected = text
        abbreviations = ["Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "vs.", "etc.", "i.e.", "e.g."]
        for i, abbr in enumerate(abbreviations):
            protected = protected.replace(abbr, f"__ABBR{i}__")

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

        # Restore abbreviations
        result = []
        for sent in sentences:
            for i, abbr in enumerate(abbreviations):
                sent = sent.replace(f"__ABBR{i}__", abbr)
            result.append(sent)

        return result


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
