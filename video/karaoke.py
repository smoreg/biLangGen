"""Karaoke subtitle rendering with word-by-word highlighting."""

import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# Find a suitable font
def get_default_font(size: int = 48) -> ImageFont.FreeTypeFont:
    """Get a default font that works cross-platform."""
    font_paths = [
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Fallback to default
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


class KaraokeRenderer:
    """Renders karaoke-style subtitles with word highlighting."""

    def __init__(
        self,
        size: Tuple[int, int] = (1920, 1080),
        font_size: int = 48,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        highlight_color: Tuple[int, int, int] = (255, 255, 0),
        outline_color: Tuple[int, int, int] = (0, 0, 0),
        outline_width: int = 3,
        line_spacing: int = 20,
        bottom_margin: int = 100,
    ):
        """
        Initialize karaoke renderer.

        Args:
            size: Video resolution (width, height)
            font_size: Font size for subtitles
            text_color: Default text color (RGB)
            highlight_color: Highlighted word color (RGB)
            outline_color: Text outline color (RGB)
            outline_width: Outline stroke width
            line_spacing: Space between lines
            bottom_margin: Margin from bottom of screen
        """
        self.size = size
        self.font_size = font_size
        self.text_color = text_color
        self.highlight_color = highlight_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.line_spacing = line_spacing
        self.bottom_margin = bottom_margin
        self.font = get_default_font(font_size)

    def _calculate_word_timings(
        self,
        sentence: str,
        duration: float,
    ) -> List[Tuple[str, float, float]]:
        """
        Calculate timing for each word based on character count.

        Args:
            sentence: The sentence text
            duration: Total duration in seconds

        Returns:
            List of (word, start_time, end_time) tuples
        """
        words = sentence.split()
        if not words:
            return []

        # Calculate total characters (excluding spaces)
        total_chars = sum(len(word) for word in words)
        if total_chars == 0:
            return [(word, 0, duration) for word in words]

        timings = []
        current_time = 0

        for word in words:
            word_duration = (len(word) / total_chars) * duration
            timings.append((word, current_time, current_time + word_duration))
            current_time += word_duration

        return timings

    def _get_highlighted_word_index(
        self,
        timings: List[Tuple[str, float, float]],
        current_time: float,
    ) -> int:
        """Get index of currently highlighted word."""
        for i, (word, start, end) in enumerate(timings):
            if start <= current_time < end:
                return i
        return len(timings) - 1 if timings else -1

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int],
        text: str,
        fill: Tuple[int, int, int],
    ) -> int:
        """
        Draw text with outline and return text width.

        Args:
            draw: PIL ImageDraw object
            position: (x, y) position
            text: Text to draw
            fill: Fill color

        Returns:
            Width of drawn text
        """
        x, y = position

        # Draw outline
        for dx in range(-self.outline_width, self.outline_width + 1):
            for dy in range(-self.outline_width, self.outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text(
                        (x + dx, y + dy),
                        text,
                        font=self.font,
                        fill=self.outline_color,
                    )

        # Draw main text
        draw.text(position, text, font=self.font, fill=fill)

        # Get text width
        bbox = self.font.getbbox(text)
        return bbox[2] - bbox[0]

    def render_frame(
        self,
        sentence_source: str,
        sentence_target: str,
        current_time: float,
        source_duration: float,
        target_duration: float,
        is_source_playing: bool,
        background: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Render a single frame with karaoke subtitles.

        Args:
            sentence_source: Source language sentence
            sentence_target: Target language sentence
            current_time: Current time within the sentence
            source_duration: Duration of source audio
            target_duration: Duration of target audio
            is_source_playing: True if source is playing, False if target
            background: Optional background image array

        Returns:
            Frame as numpy array
        """
        # Create or use background
        if background is not None:
            img = Image.fromarray(background)
        else:
            img = Image.new("RGB", self.size, (0, 0, 0))

        draw = ImageDraw.Draw(img)

        # Calculate positions
        source_bbox = self.font.getbbox(sentence_source)
        target_bbox = self.font.getbbox(sentence_target)

        source_width = source_bbox[2] - source_bbox[0]
        target_width = target_bbox[2] - target_bbox[0]
        text_height = source_bbox[3] - source_bbox[1]

        # Center horizontally
        source_x = (self.size[0] - source_width) // 2
        target_x = (self.size[0] - target_width) // 2

        # Position from bottom
        target_y = self.size[1] - self.bottom_margin - text_height
        source_y = target_y - text_height - self.line_spacing

        # Determine which line is being highlighted
        if is_source_playing:
            # Highlight source, dim target
            self._render_karaoke_line(
                draw, sentence_source, source_x, source_y,
                current_time, source_duration, highlight=True
            )
            self._render_static_line(
                draw, sentence_target, target_x, target_y,
                color=(180, 180, 180)  # Dimmed
            )
        else:
            # Source done, highlight target
            self._render_static_line(
                draw, sentence_source, source_x, source_y,
                color=self.highlight_color  # Already spoken
            )
            self._render_karaoke_line(
                draw, sentence_target, target_x, target_y,
                current_time, target_duration, highlight=True
            )

        return np.array(img)

    def _render_karaoke_line(
        self,
        draw: ImageDraw.ImageDraw,
        sentence: str,
        x: int,
        y: int,
        current_time: float,
        duration: float,
        highlight: bool = True,
    ):
        """Render a line with karaoke highlighting."""
        timings = self._calculate_word_timings(sentence, duration)
        highlighted_idx = self._get_highlighted_word_index(timings, current_time)

        current_x = x
        words = sentence.split()

        for i, word in enumerate(words):
            if highlight and i <= highlighted_idx:
                color = self.highlight_color
            else:
                color = self.text_color

            width = self._draw_text_with_outline(draw, (current_x, y), word, color)
            current_x += width

            # Add space
            if i < len(words) - 1:
                space_width = self.font.getbbox(" ")[2]
                current_x += space_width

    def _render_static_line(
        self,
        draw: ImageDraw.ImageDraw,
        sentence: str,
        x: int,
        y: int,
        color: Tuple[int, int, int],
    ):
        """Render a static (non-animated) line."""
        self._draw_text_with_outline(draw, (x, y), sentence, color)
