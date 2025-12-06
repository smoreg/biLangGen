#!/usr/bin/env python3
"""
biLangGen Video - Multilingual Video Generator

Creates videos with karaoke subtitles and rare word translations.
"""

import sys
from pathlib import Path

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import LANG_CODES, TRANSLATORS, TTS_PROVIDERS
from core.text_splitter import TextSplitter
from core.translator import Translator
from core.tts_engine import TTSEngine
from audio.combiner import AudioCombiner
from analysis.word_frequency import WordFrequencyAnalyzer
from video.backgrounds import BackgroundRenderer
from video.karaoke import KaraokeRenderer
from video.word_cards import WordCardsRenderer
from video.image_gen import ImageGenerator


def parse_speed_string(speed_str: str) -> dict:
    """Parse speed string like 'ru:2.0,en:1.0' into dict."""
    if not speed_str:
        return {}
    result = {}
    for pair in speed_str.split(","):
        if ":" in pair:
            lang, speed = pair.split(":", 1)
            try:
                result[lang.strip()] = float(speed.strip())
            except ValueError:
                pass
    return result


def parse_resolution(res_str: str) -> tuple:
    """Parse resolution string like '1920x1080'."""
    try:
        w, h = res_str.lower().split("x")
        return (int(w), int(h))
    except Exception:
        return (1920, 1080)


@click.command()
@click.option("-i", "--input", "input_file", required=True, type=click.Path(exists=True), help="Input text file")
@click.option("-o", "--output", "output_file", required=True, type=click.Path(), help="Output MP4 file")
@click.option("-s", "--source-lang", default="ru", type=click.Choice(list(LANG_CODES.keys())), help="Source language")
@click.option("-t", "--target-langs", default="en", help="Target languages (comma-separated)")
@click.option("--translator", default="google", type=click.Choice(TRANSLATORS), help="Translation provider")
@click.option("--tts", default="gtts", type=click.Choice(TTS_PROVIDERS), help="TTS provider")
@click.option("--pause", default=500, type=int, help="Pause between languages (ms)")
@click.option("--sentence-pause", default=800, type=int, help="Pause between sentences (ms)")
@click.option("--speed", default="", help='Speed per language, e.g. "ru:1.5,es:1.0"')
@click.option("--cache/--no-cache", default=True, help="Enable translation cache")
@click.option("--background", default="#000000", help="Background color (hex) or 'generate'")
@click.option("--background-image", default=None, type=click.Path(), help="Background image path")
@click.option("--font-size", default=48, type=int, help="Subtitle font size")
@click.option("--resolution", default="1920x1080", help="Video resolution (e.g. 1920x1080)")
@click.option("--rare-words", default=3, type=int, help="Max rare words per sentence")
@click.option("--fps", default=24, type=int, help="Video FPS")
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
    background: str,
    background_image: str,
    font_size: int,
    resolution: str,
    rare_words: int,
    fps: int,
):
    """Generate multilingual video with karaoke subtitles."""

    target_lang_list = [lang.strip() for lang in target_langs.split(",")]
    all_langs = [source_lang] + [l for l in target_lang_list if l != source_lang]
    speed_per_lang = parse_speed_string(speed)
    video_size = parse_resolution(resolution)

    click.echo("biLangGen Video - Multilingual Video Generator")
    click.echo("=" * 50)
    click.echo(f"Input: {input_file}")
    click.echo(f"Output: {output_file}")
    click.echo(f"Languages: {source_lang} -> {', '.join(target_lang_list)}")
    click.echo(f"Resolution: {video_size[0]}x{video_size[1]}")
    click.echo("=" * 50)

    # Read input
    click.echo("\n[1/7] Reading input file...")
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Split sentences
    click.echo("[2/7] Splitting text...")
    splitter = TextSplitter(language=source_lang)
    sentences = splitter.split(text)
    click.echo(f"  Found {len(sentences)} sentences")

    if not sentences:
        click.echo("Error: No sentences found", err=True)
        sys.exit(1)

    # Generate background if requested
    if background.lower() == "generate":
        click.echo("[2.5/7] Generating AI background...")
        img_gen = ImageGenerator()
        bg_path = img_gen.generate_from_book(text, width=video_size[0], height=video_size[1])
        if bg_path:
            background_image = bg_path
            background = "#000000"
        else:
            click.echo("  Background generation failed, using black")

    # Translate
    click.echo("[3/7] Translating...")
    trans = Translator(provider=translator, cache_enabled=cache)

    translations = {source_lang: sentences}
    for target_lang in target_lang_list:
        if target_lang == source_lang:
            continue
        click.echo(f"  Translating to {LANG_CODES[target_lang]['name']}...")
        translations[target_lang] = [
            trans.translate(s, source_lang, target_lang) for s in sentences
        ]

    # Analyze rare words
    click.echo("[4/7] Analyzing rare words...")
    analyzer = WordFrequencyAnalyzer(language=target_lang_list[0], zipf_threshold=4.5)

    rare_words_per_sentence = []
    for i, sent in enumerate(translations[target_lang_list[0]]):
        rare = analyzer.get_rare_words(sent, max_words=rare_words)
        # Translate rare words back to source language
        rare_with_trans = []
        for word, score in rare:
            translation = trans.translate(word, target_lang_list[0], source_lang)
            rare_with_trans.append((word, translation))
        rare_words_per_sentence.append(rare_with_trans)

    # Generate TTS
    click.echo("[5/7] Generating audio...")
    tts_engine = TTSEngine(provider=tts)

    audio_files = []  # [{source_lang: path, target_lang: path}, ...]
    for i, sent in enumerate(sentences):
        audio = {}
        for lang in all_langs:
            text_to_speak = translations[lang][i]
            try:
                path = tts_engine.synthesize(text_to_speak, lang)
                audio[lang] = path
            except Exception as e:
                click.echo(f"  Warning: TTS failed for sentence {i+1} in {lang}: {e}")
        audio_files.append(audio)

        if (i + 1) % 10 == 0:
            click.echo(f"  {i + 1}/{len(sentences)} sentences...")

    # Combine audio
    click.echo("[6/7] Combining audio...")
    combiner = AudioCombiner(
        pause_between_langs_ms=pause,
        pause_between_sentences_ms=sentence_pause,
        speed_per_lang=speed_per_lang,
    )

    # Create audio pairs for combiner
    sentence_audio_pairs = []
    for audio in audio_files:
        sentence_audio_pairs.append(audio)

    audio_output = output_file.replace(".mp4", ".mp3")
    combiner.combine_all(sentence_audio_pairs, all_langs, audio_output)

    # Generate video
    click.echo("[7/7] Generating video...")

    from video.generator import VideoGenerator

    video_gen = VideoGenerator(
        size=video_size,
        fps=fps,
        font_size=font_size,
        background_color=background,
        background_image=background_image,
    )

    # Prepare data for video generator
    source_sentences = sentences
    target_sentences = translations[target_lang_list[0]]

    # Audio files per sentence with source/target keys
    video_audio_files = []
    for audio in audio_files:
        video_audio_files.append({
            "source": audio.get(source_lang, ""),
            "target": audio.get(target_lang_list[0], ""),
        })

    video_gen.generate(
        sentences_source=source_sentences,
        sentences_target=target_sentences,
        audio_files=video_audio_files,
        rare_words_per_sentence=rare_words_per_sentence,
        output_path=output_file,
        combined_audio_path=audio_output,
        pause_between_langs_ms=pause,
        pause_between_sentences_ms=sentence_pause,
    )

    # Cleanup
    tts_engine.cleanup()

    click.echo(f"\nDone! Video saved to: {output_file}")
    click.echo(f"Audio saved to: {audio_output}")


if __name__ == "__main__":
    main()
