"""DeepL Free provider using deep-translator."""

import os
import time

from deep_translator import DeeplTranslator

from core.translator import BaseTranslator
from core.languages import RUSSIAN, ENGLISH, SPANISH, SPANISH_LATAM


# DeepL language code mapping (DeepL uses base codes)
DEEPL_LANG_MAP = {
    RUSSIAN.code: "ru",
    ENGLISH.code: "en",
    SPANISH.code: "es",
    SPANISH_LATAM.code: "es",  # DeepL doesn't distinguish LatAm
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

            api_key = os.environ.get("DEEPL_API_KEY")
            translator = DeeplTranslator(
                api_key=api_key,
                source=src,
                target=tgt,
                use_free_api=True,
            )
            result = translator.translate(text)
            return result if result else text
        except Exception as e:
            print(f"DeepL translation error: {e}")
            return text
