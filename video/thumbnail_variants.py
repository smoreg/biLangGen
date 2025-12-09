"""Generate multiple thumbnail layout variants for A/B testing."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Optional


def load_fonts():
    """Load fonts with fallbacks."""
    try:
        return {
            "huge": ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 110),
            "large": ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 85),
            "medium": ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 65),
            "small": ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 45),
            "tiny": ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 32),
        }
    except OSError:
        try:
            return {
                "huge": ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110),
                "large": ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 85),
                "medium": ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65),
                "small": ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45),
                "tiny": ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32),
            }
        except OSError:
            default = ImageFont.load_default()
            return {"huge": default, "large": default, "medium": default, "small": default, "tiny": default}


def prepare_background(background_path: Path, width: int = 1280, height: int = 720, darken: int = 0):
    """Load and prepare background image."""
    img = Image.open(background_path)

    # Crop to aspect ratio
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    img = img.resize((width, height), Image.Resampling.LANCZOS)

    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Dark overlay (only if darken > 0)
    if darken > 0:
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, darken))
        img = Image.alpha_composite(img, overlay)

    return img


def draw_text_with_shadow(draw, pos, text, font, fill, shadow_offset=4, stroke_width=3):
    """Draw text with shadow and stroke."""
    x, y = pos
    # Shadow
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill="black")
    # Main text
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill="black")


def variant_1(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 1: Left-aligned, stacked author name, large text"""
    w, h = img.size
    m = 60  # margin

    # "AUDIOBOOK" top left
    draw_text_with_shadow(draw, (m, 30), "🎧 AUDIOBOOK", fonts["small"], "#00FFFF")

    # Author split into lines
    words = author.upper().split()
    y = 130
    for word in words:
        draw_text_with_shadow(draw, (m, y), word, fonts["huge"], "white")
        y += 105

    # Title
    draw_text_with_shadow(draw, (m, y + 20), title, fonts["medium"], "#FFD700")

    # Languages bottom
    draw_text_with_shadow(draw, (m, h - 80), f"{src_lang} → {tgt_lang}", fonts["small"], "#00FFFF")


def variant_2(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 2: Center everything, big impact"""
    w, h = img.size

    def center_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x, y), text, font, fill)

    center_text(30, "🎧 BILINGUAL AUDIOBOOK", fonts["small"], "#00FFFF")
    center_text(150, author.upper(), fonts["huge"], "white")
    center_text(280, title, fonts["large"], "#FFD700")
    center_text(h - 90, f"{src_lang} → {tgt_lang}", fonts["medium"], "#00FFFF")


def variant_3(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 3: Bottom-heavy, languages prominent"""
    w, h = img.size
    m = 60

    # Author at top
    draw_text_with_shadow(draw, (m, 50), author.upper(), fonts["large"], "white")

    # Title below
    draw_text_with_shadow(draw, (m, 150), title, fonts["medium"], "#FFD700")

    # Big language box at bottom
    box_h = 200
    overlay = Image.new('RGBA', (w, box_h), (0, 0, 0, 200))
    img.paste(overlay, (0, h - box_h), overlay)
    draw = ImageDraw.Draw(img)

    draw_text_with_shadow(draw, (m, h - 180), f"{src_lang} → {tgt_lang}", fonts["huge"], "#00FFFF")
    draw_text_with_shadow(draw, (m, h - 70), "BILINGUAL AUDIOBOOK", fonts["small"], "white")

    return img


def variant_4(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 4: Right-aligned text"""
    w, h = img.size
    m = 60

    def right_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = w - (bbox[2] - bbox[0]) - m
        draw_text_with_shadow(draw, (x, y), text, font, fill)

    right_text(30, "🎧 AUDIOBOOK", fonts["small"], "#00FFFF")

    words = author.upper().split()
    y = 130
    for word in words:
        right_text(y, word, fonts["huge"], "white")
        y += 105

    right_text(y + 20, title, fonts["medium"], "#FFD700")
    right_text(h - 80, f"{src_lang} → {tgt_lang}", fonts["small"], "#00FFFF")


def variant_5(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 5: Diagonal emphasis, author huge"""
    w, h = img.size
    m = 60

    draw_text_with_shadow(draw, (m, 40), "AUDIOBOOK", fonts["tiny"], "#00FFFF")
    draw_text_with_shadow(draw, (m, 100), author.upper(), fonts["huge"], "white", stroke_width=5)
    draw_text_with_shadow(draw, (m + 20, 220), title, fonts["large"], "#FFD700")
    draw_text_with_shadow(draw, (m + 40, 340), f"🎧 {src_lang} → {tgt_lang}", fonts["medium"], "#00FFFF")


def variant_6(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 6: Compact top bar + big center"""
    w, h = img.size

    # Top bar
    bar = Image.new('RGBA', (w, 80), (0, 200, 200, 200))
    img.paste(bar, (0, 0), bar)
    draw = ImageDraw.Draw(img)

    draw_text_with_shadow(draw, (30, 20), f"🎧 {src_lang} → {tgt_lang} AUDIOBOOK", fonts["small"], "black", shadow_offset=0, stroke_width=0)

    # Center content
    def center_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x, y), text, font, fill)

    center_text(200, author.upper(), fonts["huge"], "white")
    center_text(340, title, fonts["large"], "#FFD700")

    return img


def variant_7(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 7: Split screen feel - author left, title right"""
    w, h = img.size

    # Left side - author
    words = author.upper().split()
    y = 100
    for word in words:
        draw_text_with_shadow(draw, (50, y), word, fonts["large"], "white")
        y += 90

    # Right side - title + info
    draw_text_with_shadow(draw, (w//2 + 50, 150), title, fonts["large"], "#FFD700")
    draw_text_with_shadow(draw, (w//2 + 50, 280), f"{src_lang} → {tgt_lang}", fonts["medium"], "#00FFFF")
    draw_text_with_shadow(draw, (w//2 + 50, 380), "🎧 AUDIOBOOK", fonts["small"], "white")


def variant_8(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 8: Vertical language flags style"""
    w, h = img.size
    m = 60

    # Languages at top, very prominent
    draw_text_with_shadow(draw, (m, 30), src_lang, fonts["medium"], "#FF6B6B")
    draw_text_with_shadow(draw, (m, 100), "↓", fonts["medium"], "white")
    draw_text_with_shadow(draw, (m, 160), tgt_lang, fonts["medium"], "#4ECDC4")

    # Author + title
    draw_text_with_shadow(draw, (m, 280), author.upper(), fonts["large"], "white")
    draw_text_with_shadow(draw, (m, 390), title, fonts["medium"], "#FFD700")

    # Audiobook badge
    draw_text_with_shadow(draw, (m, h - 80), "🎧 BILINGUAL AUDIOBOOK", fonts["small"], "white")


def variant_9(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 9: Netflix style - title huge, author small"""
    w, h = img.size

    def center_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x, y), text, font, fill)

    center_text(50, f"🎧 {src_lang} → {tgt_lang}", fonts["small"], "#00FFFF")
    center_text(130, author.upper(), fonts["medium"], "#AAAAAA")
    center_text(230, title.upper(), fonts["huge"], "white")
    center_text(h - 80, "BILINGUAL AUDIOBOOK", fonts["small"], "#FFD700")


def variant_10(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 10: Podcast style - circular badge feel"""
    w, h = img.size
    m = 60

    # Top badge area
    draw_text_with_shadow(draw, (m, 30), "🎧", fonts["huge"], "white")
    draw_text_with_shadow(draw, (m + 130, 50), "AUDIOBOOK", fonts["medium"], "#00FFFF")
    draw_text_with_shadow(draw, (m + 130, 120), f"{src_lang} → {tgt_lang}", fonts["small"], "#FFD700")

    # Author and title bottom
    draw_text_with_shadow(draw, (m, h - 250), author.upper(), fonts["large"], "white")
    draw_text_with_shadow(draw, (m, h - 140), title, fonts["medium"], "#FFD700")


def variant_11(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 11: Minimalist - just essentials, huge"""
    w, h = img.size

    def center_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x, y), text, font, fill, stroke_width=4)

    center_text(180, author.upper(), fonts["huge"], "white")
    center_text(320, title, fonts["large"], "#FFD700")
    center_text(h - 100, f"🎧 {src_lang}→{tgt_lang}", fonts["medium"], "#00FFFF")


def variant_12(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 12: Book cover style - framed"""
    w, h = img.size
    m = 40

    # Draw frame
    draw.rectangle([(m, m), (w-m, h-m)], outline="#FFD700", width=4)
    draw.rectangle([(m+10, m+10), (w-m-10, h-m-10)], outline="#FFD700", width=2)

    def center_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x, y), text, font, fill)

    center_text(80, "🎧 AUDIOBOOK", fonts["tiny"], "#00FFFF")
    center_text(180, author.upper(), fonts["large"], "white")
    center_text(300, title, fonts["medium"], "#FFD700")
    center_text(h - 100, f"{src_lang} → {tgt_lang}", fonts["small"], "#00FFFF")


def variant_13(img, draw, fonts, author_en, title_en, src_lang, tgt_lang, title_ru=None, author_ru=None):
    """Layout 13: Bold left stripe - BILINGUAL LAYOUT

    Order:
    - НАЗВАНИЕ (Russian title, yellow, large)
    - автор (Russian author, gray, small)
    - TITLE (English title, yellow, large)
    - author (English author, gray, small)

    Same fonts/colors for titles, same fonts/colors for authors.
    """
    w, h = img.size

    # Dark teal color (from channel branding)
    teal_color = "#3D8B8B"

    # Left stripe
    stripe = Image.new('RGBA', (20, h), (61, 139, 139, 255))
    img.paste(stripe, (0, 0), stripe)
    draw = ImageDraw.Draw(img)

    m = 60
    max_width = w - m - 40  # Leave margin on right

    # BILINGUAL AUDIOBOOK - at top
    draw_text_with_shadow(draw, (m, 25), "🎧 BILINGUAL AUDIOBOOK", fonts["small"], teal_color)

    y = 100
    title_color = "#FFD700"  # Yellow for both titles
    author_color = "#AAAAAA"  # Gray for both authors

    # Helper to draw title with auto-sizing
    def draw_title(text, y_pos):
        title_font = fonts["large"]
        bbox = draw.textbbox((0, 0), text, font=title_font)
        title_width = bbox[2] - bbox[0]

        if title_width > max_width:
            title_font = fonts["medium"]
            bbox = draw.textbbox((0, 0), text, font=title_font)
            title_width = bbox[2] - bbox[0]

            if title_width > max_width:
                # Split into 2 lines
                words = text.split()
                mid = len(words) // 2
                line1 = " ".join(words[:mid]) if mid > 0 else words[0]
                line2 = " ".join(words[mid:]) if mid > 0 else " ".join(words[1:])

                draw_text_with_shadow(draw, (m, y_pos), line1, fonts["medium"], title_color)
                y_pos += 55
                draw_text_with_shadow(draw, (m, y_pos), line2, fonts["medium"], title_color)
                return y_pos + 60
            else:
                draw_text_with_shadow(draw, (m, y_pos), text, title_font, title_color)
                return y_pos + 70
        else:
            draw_text_with_shadow(draw, (m, y_pos), text, title_font, title_color)
            return y_pos + 85

    # --- RUSSIAN TITLE ---
    if title_ru:
        y = draw_title(title_ru, y)

    # --- RUSSIAN AUTHOR ---
    if author_ru:
        draw_text_with_shadow(draw, (m, y), author_ru, fonts["small"], author_color)
        y += 50

    y += 15  # Gap between language blocks

    # --- ENGLISH TITLE ---
    y = draw_title(title_en, y)

    # --- ENGLISH AUTHOR ---
    draw_text_with_shadow(draw, (m, y), author_en, fonts["small"], author_color)

    # Languages bottom - large
    draw_text_with_shadow(draw, (m, h - 90), f"{src_lang} → {tgt_lang}", fonts["large"], teal_color)

    return img


def variant_14(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 14: YouTube Shorts style - vertical emphasis"""
    w, h = img.size

    def center_text(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x, y), text, font, fill)

    # Stack everything vertically centered
    center_text(60, f"{src_lang}", fonts["medium"], "#FF6B6B")
    center_text(130, "↓", fonts["small"], "white")
    center_text(180, f"{tgt_lang}", fonts["medium"], "#4ECDC4")
    center_text(300, author.upper(), fonts["large"], "white")
    center_text(420, title, fonts["medium"], "#FFD700")
    center_text(h - 70, "🎧 AUDIOBOOK", fonts["small"], "white")


def variant_15(img, draw, fonts, author, title, src_lang, tgt_lang):
    """Layout 15: News/Documentary style"""
    w, h = img.size

    # Bottom third overlay
    overlay = Image.new('RGBA', (w, 250), (0, 0, 0, 220))
    img.paste(overlay, (0, h - 250), overlay)
    draw = ImageDraw.Draw(img)

    m = 50
    # Top - category
    draw_text_with_shadow(draw, (m, 30), f"🎧 {src_lang} → {tgt_lang} AUDIOBOOK", fonts["tiny"], "#00FFFF")

    # Bottom overlay content
    draw_text_with_shadow(draw, (m, h - 220), author.upper(), fonts["large"], "white")
    draw_text_with_shadow(draw, (m, h - 110), title, fonts["medium"], "#FFD700")

    return img


# Map of all variants
VARIANTS = {
    1: ("Left stacked, large", variant_1),
    2: ("Center everything", variant_2),
    3: ("Bottom language box", variant_3),
    4: ("Right-aligned", variant_4),
    5: ("Diagonal cascade", variant_5),
    6: ("Cyan top bar", variant_6),
    7: ("Split screen", variant_7),
    8: ("Vertical flags", variant_8),
    9: ("Netflix title-first", variant_9),
    10: ("Podcast badge", variant_10),
    11: ("Minimalist huge", variant_11),
    12: ("Book frame", variant_12),
    13: ("Left stripe", variant_13),
    14: ("Shorts vertical", variant_14),
    15: ("News overlay", variant_15),
}


def generate_all_variants(
    background_path: Path,
    output_dir: Path,
    author: str,
    title: str,
    source_lang: str = "RUSSIAN",
    target_lang: str = "LATAM SPANISH",
):
    """Generate all thumbnail variants."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()

    results = []
    for num, (desc, func) in VARIANTS.items():
        try:
            img = prepare_background(background_path)
            draw = ImageDraw.Draw(img)

            # Some variants return modified img
            result = func(img, draw, fonts, author, title, source_lang, target_lang)
            if result is not None:
                img = result

            output_path = output_dir / f"variant_{num:02d}.png"
            img.convert('RGB').save(output_path, quality=95)
            results.append((num, desc, output_path))
            print(f"✓ Variant {num}: {desc}")
        except Exception as e:
            print(f"✗ Variant {num}: {e}")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python thumbnail_variants.py <background.png> <output_dir> [author] [title]")
        sys.exit(1)

    bg_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    author = sys.argv[3] if len(sys.argv) > 3 else "Jorge Luis Borges"
    title = sys.argv[4] if len(sys.argv) > 4 else "Ragnarök"

    results = generate_all_variants(bg_path, out_dir, author, title)
    print(f"\nGenerated {len(results)} variants in {out_dir}")
