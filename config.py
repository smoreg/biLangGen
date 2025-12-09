"""Default configuration for makeBiAudio."""

from dataclasses import dataclass, field
from typing import Optional

from core.languages import (
    RUSSIAN, ENGLISH, SPANISH, SPANISH_LATAM,
    ALL_LANGUAGES
)


@dataclass
class Config:
    """Application configuration."""

    # Languages
    source_lang: str = RUSSIAN.code
    target_langs: list[str] = field(default_factory=lambda: [ENGLISH.code])

    # Translation
    translator: str = "openai"  # openai, google, deepl-free, deepl-pro, argos
    deepl_api_key: Optional[str] = None
    cache_translations: bool = True
    cache_file: str = ".translation_cache.json"

    # TTS
    tts_provider: str = "google_cloud"  # gtts, pyttsx3, google_cloud

    # Audio
    pause_between_langs_ms: int = 500
    pause_between_sentences_ms: int = 800
    speed_per_lang: dict[str, float] = field(default_factory=lambda: {
        RUSSIAN.code: 1.0,
        ENGLISH.code: 1.0,
        SPANISH.code: 1.0,
        SPANISH_LATAM.code: 1.0,
    })
    output_format: str = "mp3"

    # Processing
    temp_dir: str = ".temp_audio"


# Language codes mapping (uses core.languages for consistency)
LANG_CODES = {
    lang.code: {
        "name": lang.name,
        "nltk": lang.name.lower().split()[0],  # "Russian" -> "russian"
        "gtts": lang.code.split("-")[0],  # "es-latam" -> "es"
    }
    for lang in ALL_LANGUAGES
}

# Supported translators
TRANSLATORS = ["google", "deepl-free", "deepl-pro", "argos", "openai", "gemini"]

# Supported TTS providers
TTS_PROVIDERS = ["gtts", "pyttsx3", "google_cloud"]
