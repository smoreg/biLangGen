"""YouTube thumbnail generator.

Creates eye-catching thumbnails from background images with:
- Language flags (source → target)
- Author name and title
- Overlay effects for better text readability
"""

import subprocess
from pathlib import Path
from typing import Optional

# Language to flag emoji mapping
LANG_FLAGS = {
    "ru": "🇷🇺",
    "en": "🇬🇧",
    "en-US": "🇺🇸",
    "en-GB": "🇬🇧",
    "es": "🇪🇸",
    "es-latam": "🇦🇷",
    "es-ar": "🇦🇷",
    "es-mx": "🇲🇽",
    "de": "🇩🇪",
    "fr": "🇫🇷",
    "it": "🇮🇹",
    "pt": "🇵🇹",
    "pt-BR": "🇧🇷",
    "ja": "🇯🇵",
    "zh": "🇨🇳",
    "ko": "🇰🇷",
}

# Language to full name mapping
LANG_NAMES = {
    "ru": "Russian",
    "en": "English",
    "en-US": "English",
    "en-GB": "English",
    "es": "Spanish",
    "es-latam": "LATAM Spanish",
    "es-ar": "Argentine Spanish",
    "es-mx": "Mexican Spanish",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "pt-BR": "Brazilian Portuguese",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
}


def generate_thumbnail(
    background_path: Path,
    output_path: Path,
    source_lang: str,
    target_lang: str,
    author: Optional[str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
) -> Path:
    """Generate YouTube thumbnail using ffmpeg.

    Args:
        background_path: Path to background image
        output_path: Path for output thumbnail
        source_lang: Source language code (e.g., 'ru')
        target_lang: Target language code (e.g., 'es-latam')
        author: Author name (optional)
        title: Book/story title (optional)
        subtitle: Additional text like "Bilingual Audiobook" (optional)
        width: Output width (default 1280)
        height: Output height (default 720)

    Returns:
        Path to generated thumbnail
    """
    # Get flags
    src_flag = LANG_FLAGS.get(source_lang, "🌐")
    tgt_flag = LANG_FLAGS.get(target_lang, "🌐")
    lang_text = f"{src_flag}→{tgt_flag}"

    # Build filter complex
    filters = []

    # 1. Scale and crop background to exact dimensions
    filters.append(f"scale={width}:{height}:force_original_aspect_ratio=increase")
    filters.append(f"crop={width}:{height}")

    # 2. Add dark gradient overlay for better text readability
    # Bottom gradient (for title)
    filters.append(
        f"drawbox=x=0:y={height-200}:w={width}:h=200:color=black@0.6:t=fill"
    )
    # Top gradient (for language flags)
    filters.append(
        f"drawbox=x=0:y=0:w={width}:h=100:color=black@0.5:t=fill"
    )

    # 3. Add language flags text (top right)
    filters.append(
        f"drawtext=text='{lang_text}':"
        f"fontfile=/System/Library/Fonts/Apple Color Emoji.ttc:"
        f"fontsize=48:"
        f"fontcolor=white:"
        f"x={width}-tw-40:y=25:"
        f"shadowcolor=black@0.8:shadowx=2:shadowy=2"
    )

    # 4. Add "BILINGUAL" badge (top left)
    filters.append(
        f"drawtext=text='BILINGUAL':"
        f"fontfile=/System/Library/Fonts/Supplemental/Arial Bold.ttf:"
        f"fontsize=28:"
        f"fontcolor=white:"
        f"borderw=2:bordercolor=black:"
        f"x=30:y=35"
    )

    # 5. Add author name (bottom, large)
    if author:
        # Clean author name for ffmpeg
        author_clean = author.upper().replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"drawtext=text='{author_clean}':"
            f"fontfile=/System/Library/Fonts/Supplemental/Arial Bold.ttf:"
            f"fontsize=72:"
            f"fontcolor=white:"
            f"borderw=3:bordercolor=black:"
            f"x=(w-tw)/2:y={height}-170:"
            f"shadowcolor=black@0.8:shadowx=3:shadowy=3"
        )

    # 6. Add title (below author)
    if title:
        title_clean = title.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"drawtext=text='{title_clean}':"
            f"fontfile=/System/Library/Fonts/Supplemental/Arial Bold.ttf:"
            f"fontsize=48:"
            f"fontcolor=yellow:"
            f"borderw=2:bordercolor=black:"
            f"x=(w-tw)/2:y={height}-90:"
            f"shadowcolor=black@0.8:shadowx=2:shadowy=2"
        )

    # 7. Add subtitle (optional, smaller text)
    if subtitle:
        subtitle_clean = subtitle.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"drawtext=text='{subtitle_clean}':"
            f"fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:"
            f"fontsize=24:"
            f"fontcolor=white@0.9:"
            f"x=(w-tw)/2:y={height}-35"
        )

    # Combine filters
    filter_complex = ",".join(filters)

    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", str(background_path),
        "-vf", filter_complex,
        "-frames:v", "1",
        str(output_path)
    ]

    # Run ffmpeg
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def generate_thumbnail_pillow(
    background_path: Path,
    output_path: Path,
    source_lang: str,
    target_lang: str,
    author: Optional[str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
) -> Path:
    """Generate YouTube thumbnail using Pillow (better emoji/font support).

    Layout (left-aligned, like professional thumbnails):
    ┌────────────────────────────────────┐
    │                                    │
    │  BILINGUAL AUDIOBOOK               │  <- Top left, small
    │                                    │
    │  JORGE LUIS                        │  <- Author line 1 (huge, white)
    │  BORGES                            │  <- Author line 2 (huge, white)
    │                                    │
    │  Ragnarök                          │  <- Title (large, yellow)
    │                                    │
    │  🇷🇺 RUSSIAN → 🇦🇷 LATAM SPANISH   │  <- Languages (bottom left, cyan)
    └────────────────────────────────────┘

    Falls back to ffmpeg if Pillow is not available.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not installed, falling back to ffmpeg")
        return generate_thumbnail(
            background_path, output_path, source_lang, target_lang,
            author, title, subtitle, width, height
        )

    # Load and resize background
    img = Image.open(background_path)

    # Calculate crop to maintain aspect ratio
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider - crop sides
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        # Image is taller - crop top/bottom
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    img = img.resize((width, height), Image.Resampling.LANCZOS)

    # Convert to RGBA for transparency
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Create dark overlay for entire image (better text readability)
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    # Full dark overlay
    draw_overlay.rectangle([(0, 0), (width, height)], fill=(0, 0, 0, 120))

    # Bottom bar (solid dark for language info)
    bar_height = 140
    draw_overlay.rectangle([(0, height - bar_height), (width, height)], fill=(0, 0, 0, 220))

    # Composite overlay
    img = Image.alpha_composite(img, overlay)

    # Draw text
    draw = ImageDraw.Draw(img)

    # Try to load fonts
    try:
        # macOS fonts
        font_author = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 90)
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 60)
        font_lang = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 42)
        font_subtitle = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 32)
    except OSError:
        try:
            # Linux fonts
            font_author = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
            font_lang = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
            font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except OSError:
            # Fallback to default
            font_author = ImageFont.load_default()
            font_title = ImageFont.load_default()
            font_lang = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()

    # Get language names
    src_name = LANG_NAMES.get(source_lang, source_lang.upper()).upper()
    tgt_name = LANG_NAMES.get(target_lang, target_lang.upper()).upper()

    # Left margin for all text
    left_margin = 50

    # Draw "BILINGUAL AUDIOBOOK" at top left
    subtitle_text = "BILINGUAL AUDIOBOOK"
    top_y = 40
    draw.text((left_margin, top_y), subtitle_text, font=font_subtitle, fill="white",
              stroke_width=2, stroke_fill="black")

    # Draw author (left-aligned, split into lines if needed)
    if author:
        author_upper = author.upper()
        # Split author name into words for multi-line
        words = author_upper.split()

        if len(words) >= 2:
            # Two lines: first name(s) and last name
            line1 = " ".join(words[:-1])  # First name(s)
            line2 = words[-1]              # Last name

            author_y1 = 140
            author_y2 = 230

            # Line 1
            draw.text((left_margin + 4, author_y1 + 4), line1, font=font_author, fill="black")
            draw.text((left_margin, author_y1), line1, font=font_author, fill="white",
                      stroke_width=4, stroke_fill="black")

            # Line 2
            draw.text((left_margin + 4, author_y2 + 4), line2, font=font_author, fill="white")
            draw.text((left_margin, author_y2), line2, font=font_author, fill="white",
                      stroke_width=4, stroke_fill="black")

            title_y = author_y2 + 110
        else:
            # Single line author
            author_y = 180
            draw.text((left_margin + 4, author_y + 4), author_upper, font=font_author, fill="black")
            draw.text((left_margin, author_y), author_upper, font=font_author, fill="white",
                      stroke_width=4, stroke_fill="black")
            title_y = author_y + 110
    else:
        title_y = 200

    # Draw title (left-aligned, yellow)
    if title:
        draw.text((left_margin + 3, title_y + 3), title, font=font_title, fill="black")
        draw.text((left_margin, title_y), title, font=font_title, fill="#FFD700",
                  stroke_width=3, stroke_fill="black")

    # Draw language info at bottom left
    lang_text = f"{src_name}  →  {tgt_name}"
    lang_y = height - 70
    draw.text((left_margin, lang_y), lang_text, font=font_lang, fill="#00FFFF",
              stroke_width=2, stroke_fill="black")

    # Convert back to RGB for saving as JPEG/PNG
    img = img.convert('RGB')
    img.save(output_path, quality=95)

    return output_path


def generate_project_thumbnail(
    project_dir: Path,
    author: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[Path]:
    """Generate thumbnail for a project using its background image.

    Args:
        project_dir: Path to project directory
        author: Author name (optional, will try to infer from project name)
        title: Title (optional, will try to infer from project name)

    Returns:
        Path to generated thumbnail or None if no background found
    """
    import sqlite3

    # Find background image
    video_dir = project_dir / "video"
    background = None
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        candidate = video_dir / f"background{ext}"
        if candidate.exists():
            background = candidate
            break

    if not background:
        print(f"No background image found in {video_dir}")
        return None

    # Get language info from database
    db_path = project_dir / "project.db"
    if not db_path.exists():
        print(f"No project.db found in {project_dir}")
        return None

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT key, value FROM meta")
    meta = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    source_lang = meta.get("source_lang", "ru")
    target_lang = meta.get("target_lang", "es")

    # Try to get more specific language from project folder name
    # e.g., "asimov_profession_ru_es-latam" -> target is "es-latam" not just "es"
    project_name = project_dir.name
    name_parts = project_name.rsplit("_", 2)
    if len(name_parts) >= 3:
        folder_source = name_parts[-2]
        folder_target = name_parts[-1]
        # Use folder language if it's more specific (e.g., es-latam vs es)
        if folder_target.startswith(target_lang) and len(folder_target) > len(target_lang):
            target_lang = folder_target
        if folder_source.startswith(source_lang) and len(folder_source) > len(source_lang):
            source_lang = folder_source

    # Try to infer author/title from project name if not provided
    if not author and not title:
        # Parse project name like "asimov_profession_ru_es-latam"
        parts = project_name.rsplit("_", 2)
        if len(parts) >= 3:
            name_part = parts[0]
            # Try to split into author and title
            name_parts = name_part.split("_", 1)
            if len(name_parts) == 2:
                author = name_parts[0].title()
                title = name_parts[1].replace("_", " ").title()
            else:
                title = name_part.replace("_", " ").title()

    # Generate thumbnail
    output_path = video_dir / "thumbnail.png"

    try:
        generate_thumbnail_pillow(
            background_path=background,
            output_path=output_path,
            source_lang=source_lang,
            target_lang=target_lang,
            author=author,
            title=title,
            subtitle="Bilingual Audiobook",
        )
        print(f"Generated thumbnail: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python thumbnail_generator.py <project_dir> [author] [title]")
        print("Example: python thumbnail_generator.py projects/asimov_profession_ru_es-latam 'Isaac Asimov' 'Profession'")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    author = sys.argv[2] if len(sys.argv) > 2 else None
    title = sys.argv[3] if len(sys.argv) > 3 else None

    result = generate_project_thumbnail(project_dir, author, title)
    if result:
        print(f"Success: {result}")
    else:
        print("Failed to generate thumbnail")
        sys.exit(1)
