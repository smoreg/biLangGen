"""Audio combining and processing module."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pydub import AudioSegment


class AudioCombiner:
    """Combines audio segments with pauses and speed control."""

    def __init__(
        self,
        pause_between_langs_ms: int = 500,
        pause_between_sentences_ms: int = 800,
        speed_per_lang: Optional[dict[str, float]] = None,
    ):
        """
        Initialize combiner.

        Args:
            pause_between_langs_ms: Pause duration between language variants (ms)
            pause_between_sentences_ms: Pause duration between sentences (ms)
            speed_per_lang: Speed multiplier per language, e.g. {"ru": 2.0, "en": 1.0}
        """
        self.pause_between_langs_ms = pause_between_langs_ms
        self.pause_between_sentences_ms = pause_between_sentences_ms
        self.speed_per_lang = speed_per_lang or {}

    def _create_silence(self, duration_ms: int) -> AudioSegment:
        """Create silence of specified duration."""
        return AudioSegment.silent(duration=duration_ms)

    def _change_speed_preserve_pitch(
        self, audio_path: str, speed: float, output_path: str
    ) -> str:
        """
        Change audio speed without changing pitch using rubberband.

        Args:
            audio_path: Input audio file path
            speed: Speed multiplier (2.0 = 2x faster)
            output_path: Output audio file path

        Returns:
            Output file path
        """
        if speed == 1.0:
            # No change needed
            return audio_path

        try:
            # Try using rubberband-cli
            result = subprocess.run(
                [
                    "rubberband",
                    "--tempo", str(speed),
                    "--pitch", "1.0",  # Keep pitch unchanged
                    audio_path,
                    output_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return output_path
        except FileNotFoundError:
            pass

        try:
            # Fallback to ffmpeg with atempo filter
            # atempo filter accepts values 0.5-2.0, so chain multiple for higher speeds
            tempo_filters = self._build_atempo_filter(speed)
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", audio_path,
                    "-filter:a", tempo_filters,
                    "-vn",
                    output_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return output_path
        except FileNotFoundError:
            pass

        # If both fail, return original
        print(f"Warning: Could not change speed. Install rubberband or ffmpeg.")
        return audio_path

    def _build_atempo_filter(self, speed: float) -> str:
        """
        Build ffmpeg atempo filter chain for any speed value.
        atempo accepts 0.5-2.0, so we chain multiple for values outside this range.
        """
        if speed <= 0:
            speed = 1.0

        filters = []
        remaining = speed

        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0

        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5

        if remaining != 1.0:
            filters.append(f"atempo={remaining:.4f}")

        return ",".join(filters) if filters else "atempo=1.0"

    def _load_and_process_audio(self, audio_path: str, language: str) -> AudioSegment:
        """Load audio file and apply speed change if needed."""
        speed = self.speed_per_lang.get(language, 1.0)

        if speed != 1.0:
            # Apply speed change
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                processed_path = self._change_speed_preserve_pitch(
                    audio_path, speed, tmp.name
                )
                audio = AudioSegment.from_file(processed_path)
                # Clean up temp file if it was created
                if processed_path != audio_path:
                    try:
                        Path(processed_path).unlink()
                    except OSError:
                        pass
        else:
            audio = AudioSegment.from_file(audio_path)

        return audio

    def combine_sentence_pair(
        self,
        audio_files: dict[str, str],  # {lang: file_path}
        languages_order: list[str],
    ) -> AudioSegment:
        """
        Combine audio files for one sentence in multiple languages.

        Args:
            audio_files: Dict mapping language to audio file path
            languages_order: Order of languages to combine

        Returns:
            Combined AudioSegment
        """
        combined = AudioSegment.empty()
        lang_pause = self._create_silence(self.pause_between_langs_ms)

        for i, lang in enumerate(languages_order):
            if lang not in audio_files:
                continue

            audio = self._load_and_process_audio(audio_files[lang], lang)
            combined += audio

            # Add pause between languages (not after last one)
            if i < len(languages_order) - 1:
                combined += lang_pause

        return combined

    def combine_all(
        self,
        sentence_audio_pairs: list[dict[str, str]],
        languages_order: list[str],
        output_path: str,
    ) -> str:
        """
        Combine all sentences into final audio file.

        Args:
            sentence_audio_pairs: List of dicts mapping language to audio path
            languages_order: Order of languages for each sentence
            output_path: Output file path

        Returns:
            Path to output file
        """
        combined = AudioSegment.empty()
        sentence_pause = self._create_silence(self.pause_between_sentences_ms)

        for i, audio_files in enumerate(sentence_audio_pairs):
            sentence_audio = self.combine_sentence_pair(audio_files, languages_order)
            combined += sentence_audio

            # Add pause between sentences (not after last one)
            if i < len(sentence_audio_pairs) - 1:
                combined += sentence_pause

            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  Combined {i + 1}/{len(sentence_audio_pairs)} sentences...")

        # Export
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        combined.export(output_path, format="mp3")

        return output_path
