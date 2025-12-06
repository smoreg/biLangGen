"""Background rendering for video generation."""

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image


class BackgroundRenderer:
    """Renders video backgrounds (solid color or image)."""

    def __init__(
        self,
        size: Tuple[int, int] = (1920, 1080),
        color: str = "#000000",
        image_path: Optional[str] = None,
        darken_image: float = 0.5,
    ):
        """
        Initialize background renderer.

        Args:
            size: Video resolution (width, height)
            color: Background color in hex (default: black)
            image_path: Optional path to background image
            darken_image: Darken factor for image (0-1, lower = darker)
        """
        self.size = size
        self.color = color
        self.image_path = image_path
        self.darken_image = darken_image
        self._cached_bg: Optional[np.ndarray] = None

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _create_solid_background(self) -> np.ndarray:
        """Create solid color background."""
        rgb = self._hex_to_rgb(self.color)
        bg = np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)
        bg[:, :] = rgb
        return bg

    def _create_image_background(self) -> np.ndarray:
        """Create background from image with darkening."""
        if not self.image_path or not Path(self.image_path).exists():
            return self._create_solid_background()

        try:
            img = Image.open(self.image_path).convert("RGB")

            # Resize to fit video size (cover mode)
            img_ratio = img.width / img.height
            video_ratio = self.size[0] / self.size[1]

            if img_ratio > video_ratio:
                # Image is wider - fit height
                new_height = self.size[1]
                new_width = int(new_height * img_ratio)
            else:
                # Image is taller - fit width
                new_width = self.size[0]
                new_height = int(new_width / img_ratio)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Center crop
            left = (new_width - self.size[0]) // 2
            top = (new_height - self.size[1]) // 2
            img = img.crop((left, top, left + self.size[0], top + self.size[1]))

            # Convert to numpy array
            bg = np.array(img)

            # Darken
            bg = (bg * self.darken_image).astype(np.uint8)

            return bg

        except Exception as e:
            print(f"Error loading background image: {e}")
            return self._create_solid_background()

    def get_frame(self) -> np.ndarray:
        """
        Get background frame.

        Returns:
            numpy array of shape (height, width, 3)
        """
        if self._cached_bg is None:
            if self.image_path:
                self._cached_bg = self._create_image_background()
            else:
                self._cached_bg = self._create_solid_background()

        return self._cached_bg.copy()

    def get_pil_image(self) -> Image.Image:
        """Get background as PIL Image."""
        return Image.fromarray(self.get_frame())
