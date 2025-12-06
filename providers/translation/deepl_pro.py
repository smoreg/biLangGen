"""DeepL Pro provider (placeholder for API key version)."""

from typing import Optional

from core.translator import BaseTranslator


class DeepLProTranslator(BaseTranslator):
    """DeepL Pro with API key.

    Requires: DEEPL_API_KEY environment variable or api_key parameter.
    """

    def __init__(self, api_key: Optional[str] = None):
        import os

        self.api_key = api_key or os.environ.get("DEEPL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DeepL Pro requires API key. "
                "Set DEEPL_API_KEY environment variable or pass api_key parameter."
            )

    def name(self) -> str:
        return "DeepL Translate (Pro)"

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate using DeepL Pro API."""
        if not text.strip():
            return text

        if source_lang == target_lang:
            return text

        try:
            import deepl

            translator = deepl.Translator(self.api_key)
            result = translator.translate_text(
                text,
                source_lang=source_lang.upper(),
                target_lang=target_lang.upper(),
            )
            return result.text
        except Exception as e:
            print(f"DeepL Pro error: {e}")
            return text
