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


def _build_atempo_filter_standalone(speed: float) -> str:
    """Build ffmpeg atempo filter chain for any speed value."""
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


def _get_audio_duration_ms(audio_path: str) -> float:
    """Get audio duration in milliseconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        return float(result.stdout.strip()) * 1000
    return 0.0


def _process_audio_with_speed(audio_path: str, speed: float, output_path: str) -> str:
    """Process audio with speed change using ffmpeg."""
    if speed == 1.0:
        return audio_path
    tempo_filter = _build_atempo_filter_standalone(speed)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", audio_path, "-filter:a", tempo_filter, "-vn", output_path],
        capture_output=True, text=True
    )
    return output_path if result.returncode == 0 else audio_path


def combine_audio_streaming(
    source_files: list[str],
    target_files: list[str],
    output_path: str,
    pause_between_langs_ms: int = 500,
    pause_between_sentences_ms: int = 800,
    speed_source: float = 1.0,
    speed_target: float = 1.0,
    on_progress=None,
    # Word card audio parameters
    wordcard_files: list[list[tuple]] = None,  # List of [(tgt_audio, src_audio), ...] per sentence
    pause_before_wordcard_ms: int = 300,
    pause_between_words_ms: int = 200,
) -> tuple[str, list[dict]]:
    """
    Combine audio files using ffmpeg streaming concat (memory efficient).

    Args:
        source_files: List of source language audio file paths
        target_files: List of target language audio file paths
        output_path: Output combined audio path
        pause_between_langs_ms: Pause between source and target audio
        pause_between_sentences_ms: Pause between sentences
        speed_source: Speed multiplier for source audio
        speed_target: Speed multiplier for target audio
        on_progress: Progress callback (done, total)
        wordcard_files: Optional list of word card audio pairs per sentence
                       Each element is list of (target_word_audio, source_translation_audio)
        pause_before_wordcard_ms: Pause before word cards start
        pause_between_words_ms: Pause between word pairs

    Returns:
        Tuple of (output_path, timeline) where timeline format is:
        [{"start": float, "source_duration": float, "pause_between": float,
          "target_duration": float, "wordcard_start": float, "wordcard_duration": float,
          "end": float}, ...]
    """
    timeline = []
    current_time_ms = 0.0
    total = len(source_files)

    # Create temp directory that persists until concat is done
    temp_dir_path = Path(tempfile.mkdtemp())

    try:
        # Generate silence files
        silence_lang_file = temp_dir_path / "silence_lang.mp3"
        silence_sentence_file = temp_dir_path / "silence_sentence.mp3"

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r=44100:cl=stereo:d={pause_between_langs_ms/1000}",
            "-c:a", "libmp3lame", "-q:a", "2", str(silence_lang_file)
        ], capture_output=True)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r=44100:cl=stereo:d={pause_between_sentences_ms/1000}",
            "-c:a", "libmp3lame", "-q:a", "2", str(silence_sentence_file)
        ], capture_output=True)

        # Generate word card silence files if needed
        silence_wordcard_file = None
        silence_wordpause_file = None
        if wordcard_files:
            silence_wordcard_file = temp_dir_path / "silence_wordcard.mp3"
            silence_wordpause_file = temp_dir_path / "silence_wordpause.mp3"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"anullsrc=r=44100:cl=stereo:d={pause_before_wordcard_ms/1000}",
                "-c:a", "libmp3lame", "-q:a", "2", str(silence_wordcard_file)
            ], capture_output=True)
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"anullsrc=r=44100:cl=stereo:d={pause_between_words_ms/1000}",
                "-c:a", "libmp3lame", "-q:a", "2", str(silence_wordpause_file)
            ], capture_output=True)

        # Process all audio files and build concat list
        concat_entries = []

        for i, (src_file, tgt_file) in enumerate(zip(source_files, target_files)):
            # Track timing for timeline entry
            sentence_start_ms = current_time_ms
            src_duration_ms = 0.0
            tgt_duration_ms = 0.0
            wordcard_start_ms = 0.0
            wordcard_duration_ms = 0.0

            # Process source audio
            src_path = Path(src_file).resolve()
            if src_path.exists():
                if speed_source != 1.0:
                    processed_src = temp_dir_path / f"src_{i}.mp3"
                    _process_audio_with_speed(str(src_path), speed_source, str(processed_src))
                    src_to_use = str(processed_src)
                else:
                    src_to_use = str(src_path)

                src_duration_ms = _get_audio_duration_ms(src_to_use)
                # DEBUG: Print first entry info
                if i == 0:
                    orig_dur = _get_audio_duration_ms(str(src_path))
                    print(f"[DEBUG] Entry 0 source: orig={orig_dur/1000:.3f}s, processed={src_duration_ms/1000:.3f}s, file={src_to_use}")
                current_time_ms += src_duration_ms
                concat_entries.append(src_to_use)

            # Pause between languages
            concat_entries.append(str(silence_lang_file))
            current_time_ms += pause_between_langs_ms

            # Process target audio
            tgt_path = Path(tgt_file).resolve()
            if tgt_path.exists():
                if speed_target != 1.0:
                    processed_tgt = temp_dir_path / f"tgt_{i}.mp3"
                    _process_audio_with_speed(str(tgt_path), speed_target, str(processed_tgt))
                    tgt_to_use = str(processed_tgt)
                else:
                    tgt_to_use = str(tgt_path)

                tgt_duration_ms = _get_audio_duration_ms(tgt_to_use)
                current_time_ms += tgt_duration_ms
                concat_entries.append(tgt_to_use)

            # Process word card audio (if any)
            sentence_wordcards = wordcard_files[i] if wordcard_files and i < len(wordcard_files) else []
            if sentence_wordcards:
                # Pause before word cards
                concat_entries.append(str(silence_wordcard_file))
                current_time_ms += pause_before_wordcard_ms
                wordcard_start_ms = current_time_ms

                for word_idx, (first_file, second_file) in enumerate(sentence_wordcards):
                    # New combined format: (combined_path, None) - single file with all words
                    if second_file is None:
                        # Combined audio file for all words in sentence
                        combined_path = Path(first_file).resolve()
                        if combined_path.exists():
                            combined_dur = _get_audio_duration_ms(str(combined_path))
                            current_time_ms += combined_dur
                            wordcard_duration_ms += combined_dur
                            concat_entries.append(str(combined_path))
                    else:
                        # Legacy format: (target_word, source_translation) per word
                        tgt_word_path = Path(first_file).resolve()
                        if tgt_word_path.exists():
                            tgt_word_dur = _get_audio_duration_ms(str(tgt_word_path))
                            current_time_ms += tgt_word_dur
                            wordcard_duration_ms += tgt_word_dur
                            concat_entries.append(str(tgt_word_path))

                        # Small pause between target word and translation
                        concat_entries.append(str(silence_wordpause_file))
                        current_time_ms += pause_between_words_ms
                        wordcard_duration_ms += pause_between_words_ms

                        # Add source translation audio (e.g., Russian translation)
                        src_word_path = Path(second_file).resolve()
                        if src_word_path.exists():
                            src_word_dur = _get_audio_duration_ms(str(src_word_path))
                            current_time_ms += src_word_dur
                            wordcard_duration_ms += src_word_dur
                            concat_entries.append(str(src_word_path))

                        # Pause between word pairs (except after last)
                        if word_idx < len(sentence_wordcards) - 1:
                            concat_entries.append(str(silence_wordpause_file))
                            current_time_ms += pause_between_words_ms
                            wordcard_duration_ms += pause_between_words_ms

            sentence_end_ms = current_time_ms

            # Pause between sentences (not after last)
            if i < total - 1:
                concat_entries.append(str(silence_sentence_file))
                current_time_ms += pause_between_sentences_ms

            # Build timeline entry in expected format (times in seconds)
            timeline_entry = {
                "start": sentence_start_ms / 1000.0,
                "source_duration": src_duration_ms / 1000.0,
                "pause_between": pause_between_langs_ms / 1000.0,
                "target_duration": tgt_duration_ms / 1000.0,
                "end": sentence_end_ms / 1000.0,
            }
            # Add word card timing if present
            if wordcard_duration_ms > 0:
                timeline_entry["wordcard_start"] = wordcard_start_ms / 1000.0
                timeline_entry["wordcard_duration"] = wordcard_duration_ms / 1000.0
            timeline.append(timeline_entry)

            if on_progress and (i + 1) % 10 == 0:
                on_progress(i + 1, total)

        # Write concat file
        concat_list_file = temp_dir_path / "concat.txt"
        with open(concat_list_file, "w") as f:
            for file_path in concat_entries:
                f.write(f"file '{file_path}'\n")

        # Combine using ffmpeg concat
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list_file), "-c:a", "libmp3lame", "-q:a", "2", str(output_path)
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")

        if on_progress:
            on_progress(total, total)

    finally:
        # Cleanup temp directory
        import shutil
        shutil.rmtree(temp_dir_path, ignore_errors=True)

    return str(output_path), timeline


def combine_audio_parallel(
    source_files: list[str],
    target_files: list[str],
    output_path: str,
    pause_between_langs_ms: int = 500,
    pause_between_sentences_ms: int = 800,
    speed_source: float = 1.0,
    speed_target: float = 1.0,
    num_workers: int = 4,
    on_progress=None,
    # Word card audio parameters
    wordcard_files: list[list[tuple]] = None,
    pause_before_wordcard_ms: int = 300,
    pause_between_words_ms: int = 200,
) -> tuple[str, list[dict]]:
    """
    Combine audio files using parallel chunk processing.

    Delegates to streaming version since ffmpeg concat is already fast.
    """
    return combine_audio_streaming(
        source_files=source_files,
        target_files=target_files,
        output_path=output_path,
        pause_between_langs_ms=pause_between_langs_ms,
        pause_between_sentences_ms=pause_between_sentences_ms,
        speed_source=speed_source,
        speed_target=speed_target,
        on_progress=on_progress,
        wordcard_files=wordcard_files,
        pause_before_wordcard_ms=pause_before_wordcard_ms,
        pause_between_words_ms=pause_between_words_ms,
    )


def verify_and_correct_timeline(timeline: list[dict], audio_path: str) -> list[dict]:
    """Verify timeline against actual audio duration and correct if needed."""
    actual_duration_ms = _get_audio_duration_ms(audio_path)
    actual_duration_sec = actual_duration_ms / 1000.0

    if not timeline:
        return timeline

    # Get expected duration from timeline (in seconds)
    expected_duration_sec = 0.0
    for entry in timeline:
        expected_duration_sec = max(expected_duration_sec, entry.get("end", 0))

    if expected_duration_sec <= 0:
        return timeline

    # If difference is significant (>1 second), scale timeline
    if abs(actual_duration_sec - expected_duration_sec) > 1.0:
        scale = actual_duration_sec / expected_duration_sec
        for entry in timeline:
            entry["start"] = entry.get("start", 0) * scale
            entry["source_duration"] = entry.get("source_duration", 0) * scale
            entry["target_duration"] = entry.get("target_duration", 0) * scale
            entry["end"] = entry.get("end", 0) * scale
            # Scale word card timing if present
            if "wordcard_start" in entry:
                entry["wordcard_start"] = entry.get("wordcard_start", 0) * scale
            if "wordcard_duration" in entry:
                entry["wordcard_duration"] = entry.get("wordcard_duration", 0) * scale
            # pause_between stays the same (it's a constant)

    return timeline
