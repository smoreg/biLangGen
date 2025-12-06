"""Translation abstraction layer."""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class BaseTranslator(ABC):
    """Abstract base class for translators."""

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text from source to target language.

        Args:
            text: Text to translate
            source_lang: Source language code (ru, en, es)
            target_lang: Target language code (ru, en, es)

        Returns:
            Translated text
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return translator name."""
        pass


class TranslationCache:
    """Simple JSON-based translation cache."""

    def __init__(self, cache_file: str = ".translation_cache.json"):
        self.cache_file = Path(cache_file)
        self._cache: dict = {}
        self._load()

    def _load(self) -> None:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # Ignore cache save errors

    def _make_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Create cache key."""
        return f"{source_lang}:{target_lang}:{text}"

    def get(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Get cached translation."""
        key = self._make_key(text, source_lang, target_lang)
        return self._cache.get(key)

    def set(self, text: str, source_lang: str, target_lang: str, translation: str) -> None:
        """Cache translation."""
        key = self._make_key(text, source_lang, target_lang)
        self._cache[key] = translation
        self._save()


class Translator:
    """Main translator class with caching support."""

    def __init__(
        self,
        provider: str = "google",
        cache_enabled: bool = True,
        cache_file: str = ".translation_cache.json",
        deepl_api_key: Optional[str] = None,
    ):
        """
        Initialize translator.

        Args:
            provider: Translation provider (google, deepl-free, deepl-pro)
            cache_enabled: Enable translation caching
            cache_file: Path to cache file
            deepl_api_key: DeepL API key (for deepl-pro)
        """
        self.provider_name = provider
        self._translator = self._create_translator(provider, deepl_api_key)
        self._cache = TranslationCache(cache_file) if cache_enabled else None

    def _create_translator(self, provider: str, api_key: Optional[str] = None) -> BaseTranslator:
        """Create translator instance based on provider."""
        if provider == "google":
            from providers.translation.google_free import GoogleFreeTranslator

            return GoogleFreeTranslator()
        elif provider == "deepl-free":
            from providers.translation.deepl_free import DeepLFreeTranslator

            return DeepLFreeTranslator()
        elif provider == "deepl-pro":
            from providers.translation.deepl_pro import DeepLProTranslator

            return DeepLProTranslator(api_key=api_key)
        else:
            raise ValueError(f"Unknown translator provider: {provider}")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text with caching.

        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Translated text
        """
        # Skip if same language
        if source_lang == target_lang:
            return text

        # Check cache
        if self._cache:
            cached = self._cache.get(text, source_lang, target_lang)
            if cached:
                return cached

        # Translate
        translation = self._translator.translate(text, source_lang, target_lang)

        # Cache result
        if self._cache:
            self._cache.set(text, source_lang, target_lang, translation)

        return translation

    def translate_batch(
        self, texts: list[str], source_lang: str, target_lang: str
    ) -> list[str]:
        """
        Translate multiple texts.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translated texts
        """
        return [self.translate(text, source_lang, target_lang) for text in texts]
