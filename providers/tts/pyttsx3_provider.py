"""Offline TTS provider using pyttsx3."""

from pathlib import Path

from core.tts_engine import BaseTTS


class Pyttsx3Provider(BaseTTS):
    """Offline TTS using pyttsx3 with espeak-ng backend."""

    def __init__(self):
        import pyttsx3

        self._engine = pyttsx3.init()
        # Adjust rate for clarity
        self._engine.setProperty("rate", 150)

    def name(self) -> str:
        return "pyttsx3 (Offline)"

    def supported_languages(self) -> list[str]:
        # espeak-ng supports many languages
        return ["ru", "en", "es"]

    def synthesize(self, text: str, language: str, output_path: str) -> bool:
        """
        Synthesize speech using pyttsx3.

        Note: Language switching in pyttsx3 depends on available voices.
        Quality is lower than online services.

        Args:
            text: Text to synthesize
            language: Language code
            output_path: Path to save audio file

        Returns:
            True if successful
        """
        if not text.strip():
            return False

        try:
            # Try to set voice for language
            voices = self._engine.getProperty("voices")
            for voice in voices:
                if language in voice.id.lower() or language in voice.name.lower():
                    self._engine.setProperty("voice", voice.id)
                    break

            # Ensure directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            self._engine.save_to_file(text, output_path)
            self._engine.runAndWait()
            return True
        except Exception as e:
            print(f"pyttsx3 error: {e}")
            return False
