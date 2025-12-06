#!/usr/bin/env python3
"""
makeBiAudio - Multilingual Audiobook Generator

Creates audiobooks with sentences in multiple languages.
Example: sentence in Russian → same sentence in Spanish → next sentence...
"""

import sys
from pathlib import Path

import click

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, LANG_CODES, TRANSLATORS, TTS_PROVIDERS
from core.text_splitter import TextSplitter
from core.translator import Translator
from core.tts_engine import TTSEngine
from audio.combiner import AudioCombiner


def parse_speed_string(speed_str: str) -> dict[str, float]:
    """
    Parse speed string like "ru:2.0,en:1.0,es:1.0" into dict.
    """
    if not speed_str:
        return {}

    result = {}
    for pair in speed_str.split(","):
        pair = pair.strip()
        if ":" in pair:
            lang, speed = pair.split(":", 1)
            try:
                result[lang.strip()] = float(speed.strip())
            except ValueError:
                pass
    return result


@click.command()
@click.option(
    "-i", "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True),
    help="Input text file",
)
@click.option(
    "-o", "--output",
    "output_file",
    required=True,
    type=click.Path(),
    help="Output MP3 file path",
)
@click.option(
    "-s", "--source-lang",
    default="ru",
    type=click.Choice(list(LANG_CODES.keys())),
    help="Source language (default: ru)",
)
@click.option(
    "-t", "--target-langs",
    default="en",
    help="Target languages, comma-separated (default: en)",
)
@click.option(
    "--translator",
    default="google",
    type=click.Choice(TRANSLATORS),
    help="Translation provider (default: google)",
)
@click.option(
    "--tts",
    default="gtts",
    type=click.Choice(TTS_PROVIDERS),
    help="TTS provider (default: gtts)",
)
@click.option(
    "--pause",
    default=500,
    type=int,
    help="Pause between languages in ms (default: 500)",
)
@click.option(
    "--sentence-pause",
    default=800,
    type=int,
    help="Pause between sentences in ms (default: 800)",
)
@click.option(
    "--speed",
    default="",
    help='Speed per language, e.g. "ru:2.0,en:1.0" (default: 1.0 for all)',
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Enable translation caching (default: enabled)",
)
@click.option(
    "--deepl-key",
    envvar="DEEPL_API_KEY",
    help="DeepL API key (for deepl-pro provider)",
)
def main(
    input_file: str,
    output_file: str,
    source_lang: str,
    target_langs: str,
    translator: str,
    tts: str,
    pause: int,
    sentence_pause: int,
    speed: str,
    cache: bool,
    deepl_key: str,
):
    """
    Generate multilingual audiobook from text file.

    Example:
        python main.py -i book.txt -o audiobook.mp3 -s ru -t es --speed "ru:2.0,es:1.0"
    """
    # Parse target languages
    target_lang_list = [lang.strip() for lang in target_langs.split(",")]

    # All languages in order (source first, then targets)
    all_langs = [source_lang] + [l for l in target_lang_list if l != source_lang]

    # Parse speed settings
    speed_per_lang = parse_speed_string(speed)

    click.echo(f"makeBiAudio - Multilingual Audiobook Generator")
    click.echo(f"=" * 50)
    click.echo(f"Input: {input_file}")
    click.echo(f"Output: {output_file}")
    click.echo(f"Languages: {source_lang} -> {', '.join(target_lang_list)}")
    click.echo(f"Translator: {translator}")
    click.echo(f"TTS: {tts}")
    click.echo(f"Pauses: {pause}ms (lang), {sentence_pause}ms (sentence)")
    if speed_per_lang:
        click.echo(f"Speed: {speed_per_lang}")
    click.echo(f"=" * 50)

    # Read input text
    click.echo("\n[1/5] Reading input file...")
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Split into sentences
    click.echo("[2/5] Splitting text into sentences...")
    splitter = TextSplitter(language=source_lang)
    sentences = splitter.split(text)
    click.echo(f"  Found {len(sentences)} sentences")

    if not sentences:
        click.echo("Error: No sentences found in input file", err=True)
        sys.exit(1)

    # Initialize components
    click.echo("[3/5] Translating sentences...")
    trans = Translator(
        provider=translator,
        cache_enabled=cache,
        deepl_api_key=deepl_key,
    )

    # Translate sentences
    translations = {}  # {lang: [sentences]}
    translations[source_lang] = sentences

    for target_lang in target_lang_list:
        if target_lang == source_lang:
            continue

        click.echo(f"  Translating to {LANG_CODES[target_lang]['name']}...")
        translated = []
        for i, sentence in enumerate(sentences):
            trans_text = trans.translate(sentence, source_lang, target_lang)
            translated.append(trans_text)
            if (i + 1) % 10 == 0:
                click.echo(f"    {i + 1}/{len(sentences)} sentences translated")

        translations[target_lang] = translated

    # Generate TTS
    click.echo("[4/5] Generating audio...")
    tts_engine = TTSEngine(provider=tts)

    # Generate audio for each sentence in each language
    sentence_audio_pairs = []  # list of {lang: audio_path}

    for i, sentence in enumerate(sentences):
        audio_files = {}

        for lang in all_langs:
            text_to_speak = translations[lang][i]
            try:
                audio_path = tts_engine.synthesize(text_to_speak, lang)
                audio_files[lang] = audio_path
            except Exception as e:
                click.echo(f"  Warning: TTS failed for sentence {i + 1} in {lang}: {e}")
                continue

        sentence_audio_pairs.append(audio_files)

        if (i + 1) % 10 == 0:
            click.echo(f"  {i + 1}/{len(sentences)} sentences generated")

    # Combine audio
    click.echo("[5/5] Combining audio files...")
    combiner = AudioCombiner(
        pause_between_langs_ms=pause,
        pause_between_sentences_ms=sentence_pause,
        speed_per_lang=speed_per_lang,
    )

    output_path = combiner.combine_all(
        sentence_audio_pairs,
        all_langs,
        output_file,
    )

    # Cleanup temp files
    tts_engine.cleanup()

    click.echo(f"\nDone! Output saved to: {output_path}")


if __name__ == "__main__":
    main()
