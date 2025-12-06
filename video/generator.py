"""Main video generator that combines all components."""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from pydub import AudioSegment

try:
    # MoviePy 2.x
    from moviepy import AudioFileClip, ImageClip, VideoClip
except ImportError:
    # MoviePy 1.x
    from moviepy.editor import AudioFileClip, ImageClip, VideoClip

from .backgrounds import BackgroundRenderer
from .karaoke import KaraokeRenderer
from .word_cards import WordCardsRenderer


class VideoGenerator:
    """Generates video with karaoke subtitles and word cards."""

    def __init__(
        self,
        size: Tuple[int, int] = (1920, 1080),
        fps: int = 24,
        font_size: int = 48,
        word_card_font_size: int = 36,
        background_color: str = "#000000",
        background_image: Optional[str] = None,
    ):
        """
        Initialize video generator.

        Args:
            size: Video resolution (width, height)
            fps: Frames per second
            font_size: Subtitle font size
            word_card_font_size: Word card font size
            background_color: Background color (hex)
            background_image: Optional path to background image
        """
        self.size = size
        self.fps = fps

        # Initialize renderers
        self.background = BackgroundRenderer(
            size=size,
            color=background_color,
            image_path=background_image,
        )

        self.karaoke = KaraokeRenderer(
            size=size,
            font_size=font_size,
        )

        self.word_cards = WordCardsRenderer(
            size=size,
            font_size=word_card_font_size,
        )

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds."""
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0

    def _create_sentence_clip(
        self,
        sentence_source: str,
        sentence_target: str,
        audio_source_path: str,
        audio_target_path: str,
        rare_words: List[Tuple[str, str]],
        pause_between_langs_ms: int = 500,
    ) -> Tuple[List[np.ndarray], float]:
        """
        Create frames for one sentence pair.

        Returns:
            Tuple of (list of frames, total duration in seconds)
        """
        source_duration = self._get_audio_duration(audio_source_path)
        target_duration = self._get_audio_duration(audio_target_path)
        pause_duration = pause_between_langs_ms / 1000.0

        total_duration = source_duration + pause_duration + target_duration
        num_frames = int(total_duration * self.fps)

        frames = []
        frame_duration = 1.0 / self.fps

        for i in range(num_frames):
            current_time = i * frame_duration

            # Get background
            bg_frame = self.background.get_frame()

            # Add word cards
            frame_with_cards = self.word_cards.overlay_on_frame(bg_frame, rare_words)

            # Determine which audio is playing
            if current_time < source_duration:
                # Source playing
                frame = self.karaoke.render_frame(
                    sentence_source=sentence_source,
                    sentence_target=sentence_target,
                    current_time=current_time,
                    source_duration=source_duration,
                    target_duration=target_duration,
                    is_source_playing=True,
                    background=frame_with_cards,
                )
            elif current_time < source_duration + pause_duration:
                # Pause between languages
                frame = self.karaoke.render_frame(
                    sentence_source=sentence_source,
                    sentence_target=sentence_target,
                    current_time=source_duration,  # Show all source highlighted
                    source_duration=source_duration,
                    target_duration=target_duration,
                    is_source_playing=True,
                    background=frame_with_cards,
                )
            else:
                # Target playing
                target_time = current_time - source_duration - pause_duration
                frame = self.karaoke.render_frame(
                    sentence_source=sentence_source,
                    sentence_target=sentence_target,
                    current_time=target_time,
                    source_duration=source_duration,
                    target_duration=target_duration,
                    is_source_playing=False,
                    background=frame_with_cards,
                )

            frames.append(frame)

        return frames, total_duration

    def generate(
        self,
        sentences_source: List[str],
        sentences_target: List[str],
        audio_files: List[Dict[str, str]],  # [{"source": path, "target": path}, ...]
        rare_words_per_sentence: List[List[Tuple[str, str]]],
        output_path: str,
        combined_audio_path: str,
        pause_between_langs_ms: int = 500,
        pause_between_sentences_ms: int = 800,
    ) -> str:
        """
        Generate complete video.

        Args:
            sentences_source: List of source language sentences
            sentences_target: List of target language sentences
            audio_files: List of dicts with audio paths per sentence
            rare_words_per_sentence: List of rare word tuples per sentence
            output_path: Output video path
            combined_audio_path: Path to combined audio file
            pause_between_langs_ms: Pause between languages
            pause_between_sentences_ms: Pause between sentences

        Returns:
            Path to generated video
        """
        print(f"[Video] Generating video frames...")

        all_frames = []
        total_sentences = len(sentences_source)

        for i, (sent_src, sent_tgt) in enumerate(zip(sentences_source, sentences_target)):
            audio_src = audio_files[i].get("source", "")
            audio_tgt = audio_files[i].get("target", "")
            rare_words = rare_words_per_sentence[i] if i < len(rare_words_per_sentence) else []

            if not audio_src or not audio_tgt:
                continue

            frames, duration = self._create_sentence_clip(
                sentence_source=sent_src,
                sentence_target=sent_tgt,
                audio_source_path=audio_src,
                audio_target_path=audio_tgt,
                rare_words=rare_words,
                pause_between_langs_ms=pause_between_langs_ms,
            )

            all_frames.extend(frames)

            # Add pause frames between sentences
            if i < total_sentences - 1:
                pause_frames = int((pause_between_sentences_ms / 1000.0) * self.fps)
                pause_frame = self.background.get_frame()
                all_frames.extend([pause_frame] * pause_frames)

            if (i + 1) % 5 == 0:
                print(f"  Processed {i + 1}/{total_sentences} sentences...")

        print(f"[Video] Creating video from {len(all_frames)} frames...")

        # Create video from frames
        def make_frame(t):
            frame_idx = int(t * self.fps)
            if frame_idx >= len(all_frames):
                frame_idx = len(all_frames) - 1
            return all_frames[frame_idx]

        total_duration = len(all_frames) / self.fps

        # Create video clip from frames
        video_clip = VideoClip(make_frame, duration=total_duration)

        # Add audio
        print(f"[Video] Adding audio track...")
        audio_clip = AudioFileClip(combined_audio_path)

        # MoviePy 2.x uses with_* methods
        try:
            video_clip = video_clip.with_audio(audio_clip)
        except AttributeError:
            video_clip = video_clip.set_audio(audio_clip)

        # Export
        print(f"[Video] Exporting to {output_path}...")
        video_clip.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
        )

        # Cleanup
        video_clip.close()
        audio_clip.close()

        return output_path


class SimpleVideoGenerator:
    """
    Simplified video generator using direct frame-by-frame approach.

    More memory efficient for long videos.
    """

    def __init__(
        self,
        size: Tuple[int, int] = (1920, 1080),
        fps: int = 24,
        font_size: int = 48,
        background_color: str = "#000000",
        background_image: Optional[str] = None,
    ):
        self.size = size
        self.fps = fps

        self.background = BackgroundRenderer(
            size=size,
            color=background_color,
            image_path=background_image,
        )

        self.karaoke = KaraokeRenderer(size=size, font_size=font_size)
        self.word_cards = WordCardsRenderer(size=size, font_size=36)

    def generate_simple(
        self,
        sentences_data: List[dict],
        audio_path: str,
        output_path: str,
    ) -> str:
        """
        Generate video with simpler approach.

        Args:
            sentences_data: List of dicts with sentence info
            audio_path: Combined audio path
            output_path: Output video path

        Returns:
            Output path
        """
        # Uses imports from top of file

        audio = AudioFileClip(audio_path)
        duration = audio.duration

        # Precompute frame data
        def make_frame(t):
            # Find current sentence based on time
            # This is a simplified version
            bg = self.background.get_frame()
            return bg

        video = VideoClip(make_frame, duration=duration)
        video = video.set_audio(audio)

        video.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
        )

        return output_path
