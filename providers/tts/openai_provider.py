"""OpenAI Text-to-Speech provider."""

import os
import time
from pathlib import Path
from core.tts_engine import BaseTTS

try:
    from openai import OpenAI
    from openai import RateLimitError, APIError
    OPENAI_TTS_AVAILABLE = True
except ImportError:
    OPENAI_TTS_AVAILABLE = False
    RateLimitError = Exception
    APIError = Exception


# OpenAI TTS voices
# All voices work for all languages, but have different characteristics
# OpenAI TTS defaults to Latin American accent for Spanish
VOICES = {
    "alloy": "Neutral, balanced",
    "echo": "Male, warm",
    "fable": "British accent (for English)",
    "onyx": "Deep male",
    "nova": "Female, warm, friendly",
    "shimmer": "Female, expressive",
}

# Default voice per language (can be customized)
# Russian = echo (male, warm), Spanish = shimmer (female, expressive)
DEFAULT_VOICES = {
    "ru": "echo",      # Male, warm for Russian
    "es": "shimmer",   # Female, expressive for Spanish
    "es-latam": "shimmer",
    "es-ar": "shimmer",
    "es-ES": "shimmer",
    "en": "nova",
    "de": "nova",
    "fr": "nova",
    "pt": "nova",
    "it": "nova",
    "ja": "nova",
    "ko": "nova",
    "zh": "nova",
}


class OpenAITTSProvider(BaseTTS):
    """OpenAI Text-to-Speech provider.

    Pricing (Dec 2025):
    - TTS-1 (standard): $15 per 1M characters
    - TTS-1-HD (high quality): $30 per 1M characters

    Notes:
    - Spanish defaults to Latin American accent
    - No explicit locale selection (es-latam, es-MX, etc.)
    - Language is auto-detected from input text

    Voices:
    - alloy: Neutral, balanced
    - echo: Male, warm
    - fable: British accent (for English)
    - onyx: Deep male
    - nova: Female, warm, friendly (default)
    - shimmer: Female, expressive
    """

    def __init__(self, api_key: str = None, model: str = "tts-1", voice: str = "echo"):
        """
        Initialize OpenAI TTS.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY env var.
            model: TTS model - "tts-1" (standard) or "tts-1-hd" (high quality)
            voice: Default voice (alloy, echo, fable, onyx, nova, shimmer)
        """
        if not OPENAI_TTS_AVAILABLE:
            raise ImportError("openai not installed. Run: pip install openai")

        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.default_voice = voice

    def name(self) -> str:
        return "openai"

    def supported_languages(self) -> list[str]:
        # OpenAI TTS supports many languages via auto-detection
        return [
            "ru", "en", "es", "es-latam", "es-ar", "es-ES",
            "de", "fr", "it", "pt", "pt-BR",
            "ja", "ko", "zh", "nl", "pl", "tr", "vi",
            "ar", "cs", "da", "fi", "el", "he", "hi", "hu",
            "id", "ms", "no", "ro", "sk", "sv", "th", "uk",
        ]

    def synthesize(self, text: str, language: str, output_path: str) -> bool:
        """
        Synthesize speech using OpenAI TTS.

        Args:
            text: Text to synthesize
            language: Language code (auto-detected, but used for voice selection)
            output_path: Path to save MP3 file

        Returns:
            True if successful
        """
        # Select voice based on language (DEFAULT_VOICES takes priority)
        # Normalize language for voice lookup
        lang_base = language.split("-")[0] if "-" in language else language
        voice = DEFAULT_VOICES.get(language) or DEFAULT_VOICES.get(lang_base) or self.default_voice or "nova"

        # Retry with exponential backoff for rate limits
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                # Create speech
                response = self.client.audio.speech.create(
                    model=self.model,
                    voice=voice,
                    input=text,
                    response_format="mp3",
                )

                # Save to file
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                response.stream_to_file(output_path)

                # Track quota usage
                try:
                    from utils.quota_tracker import add_tts_usage
                    add_tts_usage("openai", len(text))
                except Exception:
                    pass

                return True

            except RateLimitError as e:
                delay = base_delay * (2 ** attempt)
                if attempt < max_retries - 1:
                    print(f"[OpenAI TTS] Rate limited, waiting {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    print(f"[OpenAI TTS] Max retries exceeded: {e}")
                    return False

            except APIError as e:
                print(f"[OpenAI TTS] API Error: {e}")
                return False

            except Exception as e:
                print(f"[OpenAI TTS] Error: {e}")
                return False

        return False


def list_voices():
    """List available voices with descriptions."""
    print("OpenAI TTS Voices:")
    print("-" * 40)
    for voice, desc in VOICES.items():
        print(f"  {voice}: {desc}")
    print()
    print("Note: All voices support all languages.")
    print("Spanish defaults to Latin American accent.")
