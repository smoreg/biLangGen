#!/usr/bin/env python3
"""Test OpenAI TTS for word cards - all words in one phrase."""

from pathlib import Path

# Sample word cards (target_word, source_translation)
WORDS = [
    ("Boleto", "билет"),
    ("planeta", "планета"),
    ("delgado", "тонкий"),
    ("hermoso", "красивый"),
]

def main():
    from openai import OpenAI
    from pydub import AudioSegment

    client = OpenAI()

    output_dir = Path("test_wordcards")
    output_dir.mkdir(exist_ok=True)

    # Build single phrase with all word pairs
    pairs = [f"{es} — {ru}" for es, ru in WORDS]
    phrase = ". ".join(pairs)

    print(f"Generating: {phrase}")

    card_path = output_dir / "wordcards_sample.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=phrase,
    )
    response.stream_to_file(str(card_path))

    audio = AudioSegment.from_mp3(card_path)
    print(f"\nDone! Output: {card_path}")
    print(f"Duration: {len(audio)/1000:.1f}s")

if __name__ == "__main__":
    main()
