"""Text-to-Speech abstraction layer."""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


def deterministic_hash(text: str) -> str:
    """Create deterministic hash for text (unlike Python's hash())."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


class BaseTTS(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def synthesize(self, text: str, language: str, output_path: str) -> bool:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            language: Language code (ru, en, es)
            output_path: Path to save audio file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return TTS provider name."""
        pass

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return list of supported language codes."""
        pass


class TTSEngine:
    """Main TTS engine with provider abstraction."""

    def __init__(
        self,
        provider: str = "gtts",
        temp_dir: str = ".temp_audio",
    ):
        """
        Initialize TTS engine.

        Args:
            provider: TTS provider name (gtts, pyttsx3)
            temp_dir: Directory for temporary audio files
        """
        self.provider_name = provider
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self._tts = self._create_tts(provider)

    def _create_tts(self, provider: str) -> BaseTTS:
        """Create TTS instance based on provider."""
        if provider == "gtts":
            from providers.tts.gtts_provider import GTTSProvider

            return GTTSProvider()
        elif provider == "pyttsx3":
            from providers.tts.pyttsx3_provider import Pyttsx3Provider

            return Pyttsx3Provider()
        elif provider == "google_cloud":
            from providers.tts.google_cloud_provider import GoogleCloudTTSProvider

            return GoogleCloudTTSProvider()
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")

    def synthesize(self, text: str, language: str, output_path: Optional[str] = None) -> str:
        """
        Synthesize speech.

        Args:
            text: Text to synthesize
            language: Language code
            output_path: Optional output path, generates temp file if None

        Returns:
            Path to audio file
        """
        if output_path is None:
            # Generate temp file path using deterministic hash
            text_hash = deterministic_hash(text + language)
            output_path = str(self.temp_dir / f"tts_{text_hash}.mp3")

        success = self._tts.synthesize(text, language, output_path)
        if not success:
            raise RuntimeError(f"TTS synthesis failed for: {text[:50]}...")

        return output_path

    def synthesize_batch(
        self, texts: list[str], language: str
    ) -> list[str]:
        """
        Synthesize multiple texts.

        Args:
            texts: List of texts to synthesize
            language: Language code

        Returns:
            List of paths to audio files
        """
        return [self.synthesize(text, language) for text in texts]

    def cleanup(self) -> None:
        """Remove temporary audio files."""
        if self.temp_dir.exists():
            for f in self.temp_dir.glob("tts_*.mp3"):
                try:
                    f.unlink()
                except OSError:
                    pass
