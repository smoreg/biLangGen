"""Default configuration for makeBiAudio."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    # Languages
    source_lang: str = "ru"
    target_langs: list[str] = field(default_factory=lambda: ["en"])

    # Translation
    translator: str = "google"  # google, deepl-free, deepl-pro
    deepl_api_key: Optional[str] = None
    cache_translations: bool = True
    cache_file: str = ".translation_cache.json"

    # TTS
    tts_provider: str = "gtts"  # gtts, pyttsx3, cloud

    # Audio
    pause_between_langs_ms: int = 500
    pause_between_sentences_ms: int = 800
    speed_per_lang: dict[str, float] = field(default_factory=lambda: {
        "ru": 1.0,
        "en": 1.0,
        "es": 1.0,
    })
    output_format: str = "mp3"

    # Processing
    temp_dir: str = ".temp_audio"


# Language codes mapping
LANG_CODES = {
    "ru": {"name": "Russian", "nltk": "russian", "gtts": "ru"},
    "en": {"name": "English", "nltk": "english", "gtts": "en"},
    "es": {"name": "Spanish", "nltk": "spanish", "gtts": "es"},
}

# Supported translators
TRANSLATORS = ["google", "deepl-free", "deepl-pro"]

# Supported TTS providers
TTS_PROVIDERS = ["gtts", "pyttsx3"]
