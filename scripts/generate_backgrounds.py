#!/usr/bin/env python3
"""
Generate background images for audiobook videos using Replicate API.
Uses FLUX Schnell (fast, cheap) model for budget-friendly generation.

Cost estimate for ~100 files:
- FLUX Schnell: ~$0.003 per image
- Total: ~$0.30-0.50 for all images

Usage:
    python scripts/generate_backgrounds.py                    # Process all txt files
    python scripts/generate_backgrounds.py --dry-run          # Preview without generating
    python scripts/generate_backgrounds.py --file story.txt   # Process single file
    python scripts/generate_backgrounds.py --force            # Regenerate all (delete existing)
"""

import os
import sys
import argparse
import time
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import replicate

# FLUX Schnell - fast and cheap (~$0.003/image)
# Good quality for backgrounds, 4 steps, ~2 seconds
MODEL = "black-forest-labs/flux-schnell"

# Style prompt suffix for audiobook backgrounds
STYLE_SUFFIX = """
Style: atmospheric digital art, muted colors, soft lighting, subtle gradients.
Mood: contemplative, mysterious, elegant.
Requirements: NO text, NO words, NO letters, NO typography.
Simple composition, suitable as video background with text overlay.
Dark ambient tones, cinematic quality."""

# Mapping of file patterns to themes/descriptions
# Keys can be exact filename (without extension), partial match, or folder name
STORY_THEMES = {
    # Asimov
    "asimov_nightfall": "alien world with multiple suns setting simultaneously, twilight sky with six suns, ancient observatory on hilltop",
    "asimov_bicentennial_man": "humanoid robot in contemplative pose, mechanical form transforming, blend of metal and organic",
    "asimov_caves_of_steel": "underground city with metal domes, futuristic urban landscape beneath the earth",
    "asimov_profession": "futuristic education chamber, neural learning interface, abstract knowledge visualization",
    "asimov_horovod": "circle of robots in synchronized movement, mechanical dance ritual, metallic figures in formation",

    # Belyaev
    "belyaev_amphibian": "underwater scene with human silhouette swimming among fish, bioluminescent sea creatures",
    "belyaev_douel": "surreal laboratory with floating head in glass container, retro sci-fi medical equipment",
    "belyaev_ariel": "person floating in air above cityscape, gravitational anomaly, dreamlike levitation",

    # Wells
    "wells_time_machine": "Victorian time machine with brass gears and crystal, temporal vortex surrounding it",
    "wells_war_of_worlds": "alien tripod silhouette against burning city, red weed spreading across landscape",

    # Gibson (cyberpunk)
    "gibson_johnny": "cyberpunk cityscape with neon, data courier with implants, digital rain",
    "gibson_doll": "Japanese neon alley, cybernetic geisha silhouette, rain-slicked streets",
    "gibson_backwater": "abandoned space station, derelict orbiting structure, cosmic debris",
    "gibson_agrippa": "fading digital text, dissolving memories, vintage computer terminal",

    # Sterling
    "sterling_swarm": "alien insect swarm in space, biopunk organic spacecraft, collective intelligence",
    "sterling_holy_fire": "elderly woman in transformation, rejuvenation technology, flowing energy",
    "sterling_schismatrix": "solar system habitats, posthuman civilizations, orbital structures",
    "sterling_roy": "virtual reality dissolution, digital existence, fragmented identity",
    "sterling_maneki": "Japanese lucky cat robot, blend of tradition and technology, neon shrine",
    "sterling_black_swan": "elegant Italian architecture with hidden technology, fashion and espionage",

    # Chiang
    "chiang_understand": "expanding consciousness visualization, neural networks becoming visible, transcendent intelligence",
    "chiang_division": "parallel timelines splitting, quantum reality branches, decision tree visualization",
    "chiang_like": "circular time structure, tower reaching to heaven, ancient artifact",

    # Watts
    "watts_island": "isolated research station on stormy coast, biotech laboratory, genetic engineering",
    "watts_colonel": "military command center, drone warfare interface, cold technological control",

    # Stross
    "stross_cold_war": "spy satellite network, Cold War era technology, surveillance state",
    "stross_palimpsest": "time travel agency headquarters, temporal bureaucracy, endless corridors of history",

    # Bacigalupi
    "bacigalupi_sand": "desert with buried technology, post-apocalyptic dunes, forgotten civilization",
    "bacigalupi_pop": "genetically modified organism, biopunk creature, corporate laboratory",
    "bacigalupi_flute": "calorie-restricted future, windup mechanical girl, spring-powered existence",
    "bacigalupi_pump": "water scarcity future, desperate drought landscape, precious liquid",

    # Clarke
    "clarke_sentinel": "moon surface with alien artifact, ancient pyramid on lunar landscape",
    "clarke_wind": "solar wind visualization, cosmic sailing, particles from the sun",

    # Bradbury
    "bradbury_morning": "Martian landscape at dawn, red planet with Earth sunrise, ancient ruins",
    "bradbury_rain": "endless rain on Venus, jungle planet, perpetual storm",

    # Lovecraft
    "lovecraft_crypt": "ancient crypt entrance, gothic cemetery, supernatural darkness",
    "lovecraft_dagon": "deep sea monstrosity emerging, ancient underwater temple, cosmic horror",
    "lovecraft_zann": "musician playing in attic window, otherworldly music visualization, dimensional rift",

    # Cortazar
    "cortazar_aksolotl": "axolotl in aquarium, human eye reflected, metamorphosis theme",
    "cortazar_slyuni": "suburban mystery, hidden reality beneath normalcy, liminal space",

    # Borges
    "borges_yug": "Argentine landscape, philosophical journey, infinite library concept",
    "borges_ragnarek": "Norse mythology meets modern Buenos Aires, twilight of gods",

    # Japanese
    "japanese_tales": "traditional Japanese landscape with supernatural elements, yokai folklore",
    "japanese_10nights": "dreamlike Japanese scenes, Natsume Soseki imagery, ethereal night",

    # Simak
    "simak_armistice": "alien diplomacy meeting, peace negotiation in space, two species reaching accord",
    "simak_brother": "robot and human companionship, mechanical being with soul, rural sci-fi",
    "simak_money_tree": "magical tree growing currency, surreal economics, pastoral fantasy",
    "simak_razvedka": "space exploration vessel, first contact scenario, cosmic frontier",
    "simak_svalka": "cosmic junkyard, abandoned alien artifacts, interstellar scrapheap",
    "simak": "pastoral science fiction, rural landscape with aliens, gentle first contact",

    # Poe
    "poe_purloined_letter": "Victorian study with hidden letter, detective mystery, elegant deception",
    "poe_rue_morgue": "Paris rooftops at night, brutal mystery, analytical mind",
    "poe": "gothic mystery, Victorian detective atmosphere, dark romanticism",

    # Chekhov
    "chekhov_o_lyubvi": "Russian estate in autumn, love and melancholy, emotional landscape",
    "chekhov": "Russian countryside, emotional landscape, subtle melancholy",

    # Cyberpunk anthology
    "cyberpunk_anthology": "neon-lit dystopia, corporate towers, hacker underground",
    "bethke_cyberpunk": "classic cyberpunk scene, rebellious youth with technology, street tech",
    "cyberpunk": "neon-lit dystopia, corporate towers, hacker underground",

    # Others
    "tyurin_koschei": "Russian fairy tale meets sci-fi, Koschei the Deathless reimagined, dark Slavic mythology",
    "silverberg_invisible_man": "fading human form, invisibility experiment, psychological horror",
    "silverberg_passengers": "alien possession, controlled human, body horror sci-fi",
    "silverberg": "psychological science fiction, identity dissolution, alien perspectives",
    "ohenry_last_leaf": "autumn leaves on vine, sacrifice and hope, artistic devotion",
    "ohenry": "urban emotional scene, gift of sacrifice, ironic twist",
    "zelazny_fayoli": "dimensional traveler, amber reflections, mythological power",
    "zelazny": "mythological science fiction, gods in technological age",

    # Vonnegut
    "vonnegut_piano": "retro-futuristic factory, mechanical automation, 1950s dystopia, player piano mechanism, industrial America, workers replaced by machines",
    "vonnegut": "satirical dystopia, American industrial landscape, mechanical automation, dark humor sci-fi",

    # Sheckley (folder-based detection for Russian names)
    "sheckley/романы": "absurdist space opera, satirical galactic adventure, philosophical comedy",
    "sheckley/рассказы": "absurdist short fiction, satirical future vignette, ironic sci-fi",
    "sheckley": "absurdist science fiction, satirical future society, dark comedy in space",

    # Specific Sheckley stories (Russian)
    "билет на планету транай": "utopian planet, satirical paradise, absurdist society",
    "необходимая вещь": "essential gadget from future, mysterious device, technological satire",
    "лаксианский ключ": "alien key artifact, interdimensional lock, cosmic mystery",
    "мятеж шлюпки": "rebellious spacecraft, AI uprising, small ship mutiny",
    "рейс молочного фургона": "surreal delivery route, absurdist journey, cosmic milk run",
    "призрак": "ghost in space station, haunted spacecraft, spectral sci-fi",
    "долой паразитов": "alien parasites, body invasion, satirical horror",
    "беличье колесо": "endless cycle, hamster wheel of life, existential treadmill",
    "премия за риск": "dangerous game show, lethal entertainment, dystopian TV",
    "поединок разумов": "mental battle, psychic duel, intelligence warfare",
    "травмированный": "psychological damage, mental scars, recovery journey",
    "компания необузданные таланты": "wild talents agency, chaotic superpowers, satirical business",
    "вор во времени": "temporal thief, time heist, chrono-criminal",
    "триптих": "three-panel story, triptych narrative, connected tales",
    "кое что задаром": "something for nothing, cosmic gift, ironic reward",
    "носитель инфекции": "plague carrier, space disease, quarantine horror",
    "цивилизация статуса": "status-obsessed society, social hierarchy nightmare, class satire",
    "обмен разумов": "mind swap adventure, body exchange comedy, identity chaos",
    "координаты чудес": "dimension of wonders, magical coordinates, reality shifting",
    "хождение джоэниса": "picaresque journey, satirical odyssey, absurdist travel",
    "драмокл": "space soap opera, galactic melodrama, satirical royalty",
}

def get_story_prompt(file_path: str, first_lines: str = "") -> str:
    """Generate image prompt based on filename, path, and optionally first lines of text."""
    path = Path(file_path)
    base_name = path.stem.lower()
    # Get relative path components for folder-based matching
    full_path_lower = str(path).lower()

    # Try exact match first
    if base_name in STORY_THEMES:
        theme = STORY_THEMES[base_name]
    else:
        theme = None

        # Try partial match on filename
        for key, value in STORY_THEMES.items():
            if key in base_name:
                theme = value
                break

        # Try folder-based matching (e.g., "sheckley/рассказы")
        if theme is None:
            for key, value in STORY_THEMES.items():
                if "/" in key and key in full_path_lower:
                    theme = value
                    break

        # Try partial match on path
        if theme is None:
            for key, value in STORY_THEMES.items():
                if key in full_path_lower:
                    theme = value
                    break

        # Try to detect author from path
        if theme is None:
            # Check for known author folders
            if "sheckley" in full_path_lower:
                theme = STORY_THEMES.get("sheckley")
            elif "simak" in full_path_lower:
                theme = STORY_THEMES.get("simak")
            elif "asimov" in full_path_lower:
                theme = STORY_THEMES.get("asimov_nightfall")  # Default Asimov theme
            elif "gibson" in full_path_lower:
                theme = STORY_THEMES.get("gibson_johnny")  # Default Gibson theme
            elif "sterling" in full_path_lower:
                theme = STORY_THEMES.get("sterling_swarm")
            elif "lovecraft" in full_path_lower:
                theme = STORY_THEMES.get("lovecraft_dagon")
            elif "poe" in full_path_lower:
                theme = STORY_THEMES.get("poe")
            elif "chekhov" in full_path_lower or "чехов" in full_path_lower:
                theme = STORY_THEMES.get("chekhov")

        if theme is None:
            # Fallback: generic sci-fi/literary theme
            theme = "abstract literary atmosphere, books and imagination, ethereal reading space, mysterious shadows"

    prompt = f"{theme}\n{STYLE_SUFFIX}"
    return prompt


def read_first_lines(txt_path: Path, num_lines: int = 10) -> str:
    """Read first N lines of text file for context."""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= num_lines:
                    break
                lines.append(line.strip())
            return '\n'.join(lines)
    except Exception as e:
        print(f"  Warning: couldn't read {txt_path}: {e}")
        return ""


def generate_image(prompt: str, output_path: Path, dry_run: bool = False) -> bool:
    """Generate image using Replicate FLUX Schnell model."""
    if dry_run:
        print(f"  [DRY RUN] Would generate: {output_path.name}")
        print(f"  Prompt: {prompt[:100]}...")
        return True

    try:
        output = replicate.run(
            MODEL,
            input={
                "prompt": prompt,
                "num_outputs": 1,
                "aspect_ratio": "16:9",  # Good for video backgrounds
                "output_format": "png",
                "output_quality": 90,
            }
        )

        # FLUX returns a list of FileOutput objects
        if output and len(output) > 0:
            # Download the image using requests (urllib has SSL issues on macOS)
            import requests
            image_url = output[0].url if hasattr(output[0], 'url') else str(output[0])
            response = requests.get(image_url)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            print(f"  Error: No output from model")
            return False

    except Exception as e:
        print(f"  Error generating image: {e}")
        return False


def find_txt_files(base_path: Path) -> list[Path]:
    """Find all .txt files recursively."""
    return list(base_path.rglob("*.txt"))


def main():
    parser = argparse.ArgumentParser(description="Generate background images for audiobooks")
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    parser.add_argument("--file", type=str, help="Process single file")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files that already have images")
    parser.add_argument("--path", type=str, default="txt_source", help="Path to txt files")
    args = parser.parse_args()

    # Check API token
    if not os.environ.get("REPLICATE_API_TOKEN") and not args.dry_run:
        print("Error: REPLICATE_API_TOKEN not set in environment")
        print("Add it to .env file: REPLICATE_API_TOKEN=r8_xxx")
        sys.exit(1)

    base_path = Path(args.path)
    if not base_path.exists():
        print(f"Error: Path not found: {base_path}")
        sys.exit(1)

    # Find files to process
    if args.file:
        txt_files = [base_path / args.file]
        if not txt_files[0].exists():
            print(f"Error: File not found: {txt_files[0]}")
            sys.exit(1)
    else:
        txt_files = find_txt_files(base_path)

    print(f"Found {len(txt_files)} text files")

    processed = 0
    skipped = 0
    errors = 0

    for txt_path in sorted(txt_files):
        png_path = txt_path.with_suffix(".png")

        # Check if image already exists
        if png_path.exists() and args.skip_existing:
            print(f"Skip: {txt_path.name} (image exists)")
            skipped += 1
            continue

        # Delete existing image (default behavior - regenerate all)
        if png_path.exists():
            if not args.dry_run:
                png_path.unlink()
            print(f"Deleted old: {png_path.name}")

        print(f"\nProcessing: {txt_path.name}")

        # Generate prompt
        first_lines = read_first_lines(txt_path)
        prompt = get_story_prompt(txt_path.name, first_lines)

        # Generate image
        success = generate_image(prompt, png_path, args.dry_run)

        if success:
            processed += 1
            print(f"  Generated: {png_path.name}")
        else:
            errors += 1

        # Rate limiting - Replicate limits to 6 req/min with <$5 credit
        if not args.dry_run:
            time.sleep(12)  # ~5 requests per minute to stay under limit

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Processed: {processed}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

    if not args.dry_run and processed > 0:
        # Rough cost estimate
        cost = processed * 0.003
        print(f"  Estimated cost: ${cost:.2f}")


if __name__ == "__main__":
    main()
