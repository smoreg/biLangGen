# biLangGen

Multilingual audiobook generator. Converts text into audio with sentence-by-sentence translation.

**Example**: Russian sentence → Spanish translation → next sentence...

## Features

- Sentence-by-sentence translation and audio
- Multiple language support (RU, EN, ES)
- Adjustable playback speed per language (without pitch change)
- Configurable pauses between languages
- Translation caching to avoid repeated API calls
- Rate limiting and automatic retries to prevent blocks

## Installation

```bash
# Clone repository
git clone https://github.com/smoreg/biLangGen.git
cd biLangGen

# Install dependencies
pip install -r requirements.txt

# System dependencies (macOS)
brew install ffmpeg rubberband
```

## Usage

```bash
# Basic: Russian → Spanish
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es

# With speed adjustment (1.5x for Russian, 1x for Spanish)
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --speed "ru:1.5,es:1.0"

# Multiple target languages
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t en,es

# Custom pauses
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --pause 800 --sentence-pause 1200

# Use DeepL for better translation quality
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --translator deepl-free
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input text file | Required |
| `-o, --output` | Output MP3 file | Required |
| `-s, --source-lang` | Source language (ru/en/es) | ru |
| `-t, --target-langs` | Target languages (comma-separated) | en |
| `--translator` | google / deepl-free / deepl-pro | google |
| `--tts` | gtts / pyttsx3 | gtts |
| `--pause` | Pause between languages (ms) | 500 |
| `--sentence-pause` | Pause between sentences (ms) | 800 |
| `--speed` | Speed per language, e.g. "ru:2.0,es:1.0" | 1.0 |
| `--cache/--no-cache` | Enable translation cache | enabled |

## Providers

### Translation
- **Google** (default) - Free, unlimited*, good quality
- **DeepL Free** - 500K chars/month, excellent quality
- **DeepL Pro** - Paid, excellent quality, higher limits

### TTS
- **gTTS** (default) - Free, online, good quality
- **pyttsx3** - Free, offline, basic quality

## Rate Limiting

Built-in protection against API blocks:
- Adaptive rate limiting (speeds up on success, slows down on errors)
- Exponential backoff retries (up to 5 attempts)
- Preventive pauses every 100 requests
- Translation caching to reduce API calls

## Project Structure

```
biLangGen/
├── main.py              # CLI entry point
├── config.py            # Configuration
├── core/
│   ├── text_splitter.py # Sentence tokenization
│   ├── translator.py    # Translation abstraction
│   └── tts_engine.py    # TTS abstraction
├── providers/
│   ├── translation/     # Google, DeepL providers
│   └── tts/             # gTTS, pyttsx3 providers
├── audio/
│   └── combiner.py      # Audio combining + speed control
├── utils/
│   └── rate_limiter.py  # Rate limiting utilities
└── requirements.txt
```

## License

MIT
