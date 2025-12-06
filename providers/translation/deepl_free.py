"""DeepL Free provider using deep-translator."""

import time

from deep_translator import DeeplTranslator

from core.translator import BaseTranslator


# DeepL language code mapping
DEEPL_LANG_MAP = {
    "ru": "ru",
    "en": "en",
    "es": "es",
}


class DeepLFreeTranslator(BaseTranslator):
    """Free DeepL Translate using deep-translator library.

    Note: DeepL Free has a limit of 500,000 characters per month.
    """

    MIN_DELAY_SECONDS = 1.0  # DeepL needs longer delays

    def __init__(self):
        self._last_request_time: float = 0

    def name(self) -> str:
        return "DeepL Translate (Free)"

    def _rate_limit(self) -> None:
        """Apply rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_DELAY_SECONDS:
            time.sleep(self.MIN_DELAY_SECONDS - elapsed)
        self._last_request_time = time.time()

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate using DeepL Free.

        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Translated text
        """
        if not text.strip():
            return text

        if source_lang == target_lang:
            return text

        self._rate_limit()

        try:
            src = DEEPL_LANG_MAP.get(source_lang, source_lang)
            tgt = DEEPL_LANG_MAP.get(target_lang, target_lang)

            translator = DeeplTranslator(
                source=src,
                target=tgt,
                use_free_api=True,
            )
            result = translator.translate(text)
            return result if result else text
        except Exception as e:
            print(f"DeepL translation error: {e}")
            return text
