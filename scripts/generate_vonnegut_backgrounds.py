#!/usr/bin/env python3
"""Generate backgrounds specifically for Vonnegut Player Piano chapters."""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import replicate
import requests

MODEL = "black-forest-labs/flux-schnell"

# Each chapter gets a unique but thematically consistent prompt
CHAPTER_PROMPTS = {
    1: "1950s industrial factory interior, massive machinery, control panels with analog dials, retro-futuristic automation",
    2: "american suburban neighborhood at dusk, 1950s style houses, empty streets, eerie quiet",
    3: "corporate office with early computers, punch card machines, bureaucratic dystopia, cold fluorescent lighting",
    4: "player piano in dimly lit bar, mechanical keys moving by themselves, jazz era atmosphere",
    5: "abandoned factory floor, silent conveyor belts, rust and decay, workers ghost images",
    6: "utopian planned city aerial view, geometric streets, identical houses, sterile perfection",
    7: "engineering laboratory, blueprints on walls, mechanical prototypes, cold steel surfaces",
    8: "cocktail party scene, 1950s elite society, champagne glasses, hollow smiles, art deco interior",
    9: "massive industrial complex at night, smoke stacks, electric lights, workers' housing in distance",
    10: "bar in workers' district, neon signs, worn booths, working class atmosphere",
    11: "automated assembly line, robotic arms, no humans, precision manufacturing",
    12: "country road leading to small town, pastoral landscape contrasting with distant factories",
    13: "secret meeting room, underground resistance, dim lighting, conspiratorial atmosphere",
    14: "television studio set, propaganda broadcast, fake smiles, controlled media",
    15: "unemployment office, long queues, dejected faces, bureaucratic nightmare",
    16: "luxury penthouse overlooking industrial city, wealth disparity visualization",
    17: "mechanical brain computing center, banks of machines, blinking lights, cold logic",
    18: "ghost town main street, abandoned shops, tumbleweeds, american dream decay",
    19: "protest march forming, workers gathering, tension in the air, revolutionary spirit",
    20: "executive boardroom, mahogany table, corporate power, decisions being made",
    21: "underground workshop, handmade tools, resistance technology, hope in darkness",
    22: "stadium rally, massive crowd, propaganda banners, controlled enthusiasm",
    23: "prison-like worker housing, identical apartments, surveillance feeling, no privacy",
    24: "old craftsman workshop, traditional tools, dying skills, nostalgic warmth",
    25: "highway stretching to horizon, leaving the city, escape attempt, freedom ahead",
    26: "machine graveyard, obsolete technology, rust and weeds, technological obsolescence",
    27: "revolutionary headquarters, maps on walls, planning the uprising, determined faces",
    28: "final confrontation scene, factory burning in background, chaos and destruction",
    29: "morning after destruction, smoke clearing, uncertain future, new beginning",
    30: "courtroom scene, trial of revolutionaries, justice questioned, dramatic lighting",
    31: "refugee camp outside city, displaced workers, makeshift shelters, humanity persisting",
    32: "rebuilt factory with human workers returning, hope and machinery coexisting",
    33: "family dinner scene, reconnection, simple pleasures, human warmth",
    34: "sunset over industrial landscape, transformation beginning, amber light",
    35: "dawn breaking over city, new era beginning, hope and uncertainty, final chapter mood",
}

STYLE_SUFFIX = """
Style: atmospheric digital art, muted colors, 1950s retrofuturism, cinematic.
Mood: dystopian yet hopeful, industrial melancholy.
NO text, NO words, NO letters. Simple composition for video background.
16:9 aspect ratio, dark ambient tones."""

def generate_image(prompt: str, output_path: Path) -> bool:
    """Generate image using Replicate."""
    try:
        output = replicate.run(
            MODEL,
            input={
                "prompt": prompt,
                "num_outputs": 1,
                "aspect_ratio": "16:9",
                "output_format": "png",
                "output_quality": 90,
            }
        )

        if output and len(output) > 0:
            image_url = output[0].url if hasattr(output[0], 'url') else str(output[0])
            response = requests.get(image_url)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False

def main():
    txt_source = Path("/Users/smoreg/code/makeBiAudio/txt_source")

    if not os.environ.get("REPLICATE_API_TOKEN"):
        print("Error: REPLICATE_API_TOKEN not set")
        sys.exit(1)

    print("Generating Vonnegut Player Piano backgrounds")
    print(f"Chapters: 35")
    print(f"Estimated cost: ~$0.11 (35 × $0.003)")
    print("=" * 50)

    generated = 0
    skipped = 0

    for ch_num in range(1, 36):
        txt_file = txt_source / f"vonnegut_piano_ch{ch_num:02d}.txt"
        png_file = txt_source / f"vonnegut_piano_ch{ch_num:02d}.png"

        if not txt_file.exists():
            print(f"Ch.{ch_num}: txt not found, skipping")
            continue

        if png_file.exists():
            print(f"Ch.{ch_num}: already has background, skipping")
            skipped += 1
            continue

        prompt = CHAPTER_PROMPTS.get(ch_num, CHAPTER_PROMPTS[1])
        full_prompt = f"{prompt}\n{STYLE_SUFFIX}"

        print(f"Ch.{ch_num}: generating...")

        if generate_image(full_prompt, png_file):
            print(f"  ✓ {png_file.name}")
            generated += 1
        else:
            print(f"  ✗ Failed")

        # Rate limit protection
        time.sleep(12)

    print("=" * 50)
    print(f"Generated: {generated}")
    print(f"Skipped: {skipped}")
    print(f"Cost: ~${generated * 0.003:.2f}")

if __name__ == "__main__":
    main()
