"""Rare word cards renderer for video generation."""

import os
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .karaoke import get_default_font


class WordCardsRenderer:
    """Renders rare word cards at the top of the video."""

    def __init__(
        self,
        size: Tuple[int, int] = (1920, 1080),
        font_size: int = 36,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        accent_color: Tuple[int, int, int] = (100, 200, 255),
        outline_color: Tuple[int, int, int] = (0, 0, 0),
        outline_width: int = 2,
        top_margin: int = 50,
        card_spacing: int = 15,
    ):
        """
        Initialize word cards renderer.

        Args:
            size: Video resolution (width, height)
            font_size: Font size for word cards
            text_color: Translation text color (RGB)
            accent_color: Original word color (RGB)
            outline_color: Text outline color (RGB)
            outline_width: Outline stroke width
            top_margin: Margin from top of screen
            card_spacing: Vertical space between cards
        """
        self.size = size
        self.font_size = font_size
        self.text_color = text_color
        self.accent_color = accent_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.top_margin = top_margin
        self.card_spacing = card_spacing
        self.font = get_default_font(font_size)

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int],
        text: str,
        fill: Tuple[int, int, int],
    ) -> int:
        """Draw text with outline and return width."""
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

        bbox = self.font.getbbox(text)
        return bbox[2] - bbox[0]

    def render_cards(
        self,
        rare_words: List[Tuple[str, str]],
        background: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Render word cards on background.

        Args:
            rare_words: List of (original_word, translation) tuples
            background: Optional background image array

        Returns:
            Frame with word cards as numpy array
        """
        if background is not None:
            img = Image.fromarray(background)
        else:
            img = Image.new("RGB", self.size, (0, 0, 0))

        draw = ImageDraw.Draw(img)

        if not rare_words:
            return np.array(img)

        # Calculate text height
        sample_bbox = self.font.getbbox("Ay")
        text_height = sample_bbox[3] - sample_bbox[1]

        current_y = self.top_margin

        for word, translation in rare_words:
            # Format: "📚 word → translation"
            prefix = "📚 "
            arrow = " → "

            # Calculate total width for centering
            prefix_width = self.font.getbbox(prefix)[2]
            word_width = self.font.getbbox(word)[2]
            arrow_width = self.font.getbbox(arrow)[2]
            translation_width = self.font.getbbox(translation)[2]

            total_width = prefix_width + word_width + arrow_width + translation_width
            start_x = (self.size[0] - total_width) // 2

            # Draw each part
            current_x = start_x

            # Prefix (emoji)
            self._draw_text_with_outline(
                draw, (current_x, current_y), prefix, self.text_color
            )
            current_x += prefix_width

            # Original word (accented)
            self._draw_text_with_outline(
                draw, (current_x, current_y), word, self.accent_color
            )
            current_x += word_width

            # Arrow
            self._draw_text_with_outline(
                draw, (current_x, current_y), arrow, self.text_color
            )
            current_x += arrow_width

            # Translation
            self._draw_text_with_outline(
                draw, (current_x, current_y), translation, self.text_color
            )

            current_y += text_height + self.card_spacing

        return np.array(img)

    def overlay_on_frame(
        self,
        frame: np.ndarray,
        rare_words: List[Tuple[str, str]],
    ) -> np.ndarray:
        """
        Overlay word cards on existing frame.

        Args:
            frame: Base frame as numpy array
            rare_words: List of (original_word, translation) tuples

        Returns:
            Frame with word cards overlaid
        """
        return self.render_cards(rare_words, background=frame)
