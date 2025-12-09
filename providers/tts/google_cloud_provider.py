"""Google Cloud Text-to-Speech provider."""

import os
import time
from pathlib import Path
from core.tts_engine import BaseTTS
from core.languages import (
    RUSSIAN, ENGLISH, ENGLISH_GB, SPANISH, SPANISH_LATAM,
    PORTUGUESE_BR, GERMAN, FRENCH,
    get_language, UnsupportedLanguageError
)

try:
    from google.cloud import texttospeech
    from google.api_core.exceptions import ResourceExhausted
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False
    ResourceExhausted = Exception  # Fallback


# Voice mapping for languages (Standard voices - cheaper and faster)
# Format: lang or lang-locale -> (language_code, voice_name)
#
# IMPORTANT: es and es-latam are DIFFERENT LANGUAGES:
# - es / es-ES = European Spanish (Spain)
# - es-latam / es-ar / es-US = Latin American Spanish (Argentine/Rioplatense)
#
VOICE_MAP = {
    # Russian
    "ru": ("ru-RU", "ru-RU-Standard-A"),  # Russian female
    "ru-m": ("ru-RU", "ru-RU-Standard-B"),  # Russian male

    # Spanish - Spain (European Spanish)
    "es": ("es-ES", "es-ES-Standard-A"),  # Spanish female (default)
    "es-m": ("es-ES", "es-ES-Standard-B"),  # Spanish male
    "es-ES": ("es-ES", "es-ES-Standard-A"),  # Explicit Spain
    "es-ES-m": ("es-ES", "es-ES-Standard-B"),

    # Spanish - Latin America (Argentine/Rioplatense)
    # es-US is the Google Cloud locale for Latin American Spanish
    "es-latam": ("es-US", "es-US-Standard-A"),  # LatAm female
    "es-latam-m": ("es-US", "es-US-Standard-B"),  # LatAm male
    "es-ar": ("es-US", "es-US-Standard-A"),  # Argentine alias
    "es-ar-m": ("es-US", "es-US-Standard-B"),
    "es-US": ("es-US", "es-US-Standard-A"),  # US Spanish (LatAm)
    "es-US-m": ("es-US", "es-US-Standard-B"),

    # English
    "en": ("en-US", "en-US-Standard-C"),  # US English female
    "en-m": ("en-US", "en-US-Standard-B"),  # US English male
    "en-US": ("en-US", "en-US-Standard-C"),
    "en-US-m": ("en-US", "en-US-Standard-B"),
    "en-GB": ("en-GB", "en-GB-Standard-A"),  # British female
    "en-GB-m": ("en-GB", "en-GB-Standard-B"),  # British male

    # Portuguese
    "pt": ("pt-BR", "pt-BR-Standard-A"),  # Brazilian Portuguese female
    "pt-m": ("pt-BR", "pt-BR-Standard-B"),
    "pt-BR": ("pt-BR", "pt-BR-Standard-A"),
    "pt-PT": ("pt-PT", "pt-PT-Standard-A"),  # European Portuguese

    # Other languages
    "de": ("de-DE", "de-DE-Standard-A"),
    "fr": ("fr-FR", "fr-FR-Standard-A"),
    "it": ("it-IT", "it-IT-Standard-A"),
    "ja": ("ja-JP", "ja-JP-Standard-A"),
    "ko": ("ko-KR", "ko-KR-Standard-A"),
    "zh": ("cmn-CN", "cmn-CN-Standard-A"),  # Mandarin Chinese
}


class GoogleCloudTTSProvider(BaseTTS):
    """Google Cloud Text-to-Speech provider."""

    def __init__(self, credentials_path: str = None):
        """
        Initialize Google Cloud TTS.

        Args:
            credentials_path: Path to service account JSON file.
                            If None, uses GOOGLE_APPLICATION_CREDENTIALS env var.
        """
        if not GOOGLE_TTS_AVAILABLE:
            raise ImportError("google-cloud-texttospeech not installed. Run: pip install google-cloud-texttospeech")

        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        self.client = texttospeech.TextToSpeechClient()

    def name(self) -> str:
        return "google_cloud"

    def supported_languages(self) -> list[str]:
        return list(VOICE_MAP.keys())

    def synthesize(self, text: str, language: str, output_path: str) -> bool:
        """
        Synthesize speech using Google Cloud TTS.

        Args:
            text: Text to synthesize
            language: Language code (ru, es, es-latam, en, etc.)
            output_path: Path to save MP3 file

        Returns:
            True if successful

        Raises:
            UnsupportedLanguageError: If language is not supported by this provider
        """
        # Validate language - must be in VOICE_MAP
        if language not in VOICE_MAP:
            # Try to find via aliases
            lang_obj = get_language(language)
            if lang_obj and lang_obj.code in VOICE_MAP:
                language = lang_obj.code
            else:
                raise UnsupportedLanguageError(language, "GoogleCloudTTS")

        # Get voice config
        lang_code, voice_name = VOICE_MAP[language]

        # Set up input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Set up voice
        voice = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=voice_name,
        )

        # Set up audio config (MP3)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0,
        )

        # Retry with exponential backoff for rate limits
        max_retries = 5
        base_delay = 2.0  # Start with 2 seconds

        for attempt in range(max_retries):
            try:
                # Synthesize
                response = self.client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config,
                )

                # Save to file
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.audio_content)

                # Track quota usage
                try:
                    from utils.quota_tracker import add_tts_usage
                    add_tts_usage("google_cloud", len(text))
                except Exception:
                    pass  # Don't fail synthesis if quota tracking fails

                return True

            except ResourceExhausted as e:
                # Rate limit - wait and retry
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                if attempt < max_retries - 1:
                    print(f"[GoogleTTS] Rate limited, waiting {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    print(f"[GoogleTTS] Max retries exceeded: {e}")
                    return False

            except Exception as e:
                print(f"[GoogleTTS] Error: {e}")
                return False

        return False


def list_voices(language_code: str = None):
    """List available voices."""
    if not GOOGLE_TTS_AVAILABLE:
        print("google-cloud-texttospeech not installed")
        return

    client = texttospeech.TextToSpeechClient()
    response = client.list_voices(language_code=language_code)

    for voice in response.voices:
        print(f"{voice.name}: {voice.language_codes} - {voice.ssml_gender.name}")
