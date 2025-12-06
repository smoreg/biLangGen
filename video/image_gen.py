"""AI image generation for video backgrounds."""

import hashlib
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image


class ImageGenerator:
    """
    Generates background images using free AI APIs.

    Uses Pollinations.ai - free, no API key required.
    """

    POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
    CACHE_DIR = ".image_cache"

    def __init__(self, cache_enabled: bool = True):
        """
        Initialize image generator.

        Args:
            cache_enabled: Whether to cache generated images
        """
        self.cache_enabled = cache_enabled
        self.cache_dir = Path(self.CACHE_DIR)
        if cache_enabled:
            self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, prompt: str) -> Path:
        """Get cache file path for prompt."""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        return self.cache_dir / f"bg_{prompt_hash}.jpg"

    def _clean_prompt_for_background(self, text: str, style: str = "cinematic") -> str:
        """
        Create a background-suitable prompt from text.

        Args:
            text: Source text (e.g., first paragraph of book)
            style: Visual style

        Returns:
            Optimized prompt for background generation
        """
        # Take first 200 chars and clean up
        clean_text = text[:200].strip()

        # Remove quotes and special chars
        clean_text = clean_text.replace('"', '').replace("'", "")

        # Create background-focused prompt
        prompt = (
            f"{style} atmospheric background inspired by: {clean_text}. "
            f"Dark moody lighting, subtle colors, no text, no people faces, "
            f"abstract artistic interpretation, high quality, 4k"
        )

        return prompt

    def generate(
        self,
        prompt: str,
        width: int = 1920,
        height: int = 1080,
        style: str = "cinematic",
        from_text: bool = False,
    ) -> Optional[str]:
        """
        Generate background image.

        Args:
            prompt: Text prompt or source text
            width: Image width
            height: Image height
            style: Visual style (cinematic, artistic, abstract, etc.)
            from_text: If True, treat prompt as book text and create bg prompt

        Returns:
            Path to generated image, or None on failure
        """
        if from_text:
            prompt = self._clean_prompt_for_background(prompt, style)

        # Check cache
        if self.cache_enabled:
            cache_path = self._get_cache_path(prompt)
            if cache_path.exists():
                print(f"    [ImageGen] Using cached image")
                return str(cache_path)

        # Build URL
        encoded_prompt = urllib.parse.quote(prompt)
        url = self.POLLINATIONS_URL.format(prompt=encoded_prompt)
        url += f"?width={width}&height={height}&nologo=true"

        print(f"    [ImageGen] Generating background image...")
        print(f"    [ImageGen] This may take 10-30 seconds...")

        try:
            # Download image
            headers = {"User-Agent": "Mozilla/5.0"}
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=60) as response:
                image_data = response.read()

            # Save to cache
            output_path = self._get_cache_path(prompt) if self.cache_enabled else Path(".temp_bg.jpg")

            with open(output_path, "wb") as f:
                f.write(image_data)

            # Verify it's a valid image
            img = Image.open(output_path)
            img.verify()

            print(f"    [ImageGen] Background generated: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"    [ImageGen] Generation failed: {e}")
            return None

    def generate_from_book(
        self,
        text: str,
        width: int = 1920,
        height: int = 1080,
        style: str = "cinematic",
    ) -> Optional[str]:
        """
        Generate background from book/story text.

        Args:
            text: Book text (first paragraph/chapter will be used)
            width: Image width
            height: Image height
            style: Visual style

        Returns:
            Path to generated image
        """
        return self.generate(
            prompt=text,
            width=width,
            height=height,
            style=style,
            from_text=True,
        )
