"""Argos Translate - local offline translator with pivot through English."""

import ssl
from typing import Optional

try:
    import certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass

import argostranslate.translate

from core.translator import BaseTranslator


class ArgosLocalTranslator(BaseTranslator):
    """
    Local offline translator using Argos Translate.

    Uses English as pivot language for language pairs without direct translation.
    For example: ru→es goes through ru→en→es

    Features:
    - Completely offline after model download
    - No rate limits
    - No API costs
    - ~80-85% quality of Google Translate
    """

    def __init__(self):
        """Initialize translator and cache translation functions."""
        self._translators: dict = {}
        self._check_models()

    def _check_models(self) -> None:
        """Check if required models are installed."""
        installed = argostranslate.translate.get_installed_languages()
        lang_codes = [lang.code for lang in installed]

        if not lang_codes:
            print("    [Argos] Warning: No language models installed!")
            print("    [Argos] Run: python3 -c \"import argostranslate.package; argostranslate.package.update_package_index()\"")
        else:
            print(f"    [Argos] Available languages: {', '.join(lang_codes)}")

    def name(self) -> str:
        return "Argos Translate (Local)"

    def _get_translator(self, source: str, target: str) -> Optional[callable]:
        """Get or create translation function for language pair."""
        key = f"{source}:{target}"

        if key not in self._translators:
            trans = argostranslate.translate.get_translation_from_codes(source, target)
            self._translators[key] = trans

        return self._translators[key]

    def _translate_direct(self, text: str, source: str, target: str) -> Optional[str]:
        """Try direct translation between languages."""
        translator = self._get_translator(source, target)
        if translator:
            return translator.translate(text)
        return None

    def _translate_via_pivot(self, text: str, source: str, target: str, pivot: str = "en") -> Optional[str]:
        """Translate via pivot language (usually English)."""
        # First: source → pivot
        to_pivot = self._get_translator(source, pivot)
        if not to_pivot:
            return None

        pivot_text = to_pivot.translate(text)

        # Then: pivot → target
        from_pivot = self._get_translator(pivot, target)
        if not from_pivot:
            return None

        return from_pivot.translate(pivot_text)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text using Argos Translate.

        Tries direct translation first, falls back to pivot through English.

        Args:
            text: Text to translate
            source_lang: Source language code (ru, en, es, etc.)
            target_lang: Target language code

        Returns:
            Translated text, or original if translation fails
        """
        if not text.strip():
            return text

        if source_lang == target_lang:
            return text

        # Try direct translation
        result = self._translate_direct(text, source_lang, target_lang)
        if result:
            return result

        # Fall back to pivot through English
        result = self._translate_via_pivot(text, source_lang, target_lang, pivot="en")
        if result:
            return result

        # If all fails, return original
        print(f"    [Argos] Warning: No translation path for {source_lang}→{target_lang}")
        return text

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """
        Translate multiple texts efficiently.

        Since Argos is local, no rate limiting needed.
        """
        return [self.translate(text, source_lang, target_lang) for text in texts]
