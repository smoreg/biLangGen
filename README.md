# biLangGen

Multilingual audiobook and video generator. Converts text into audio/video with sentence-by-sentence translation.

**Example**: Russian sentence → Spanish translation → next sentence...

## Features

### Audio Generation
- Sentence-by-sentence translation and audio
- Multiple language support (RU, EN, ES)
- Adjustable playback speed per language (without pitch change)
- Configurable pauses between languages
- Translation caching to avoid repeated API calls
- Rate limiting and automatic retries to prevent blocks

### Video Generation
- Karaoke-style subtitles (word highlighting during playback)
- Rare word cards with translations (1-3 words per sentence)
- Word frequency analysis to identify rare/useful vocabulary
- Customizable backgrounds (solid color or image)
- AI-generated backgrounds from text content (via Pollinations.ai)
- MP4 output optimized for YouTube

## Requirements

- Python 3.10+
- ffmpeg (for audio processing)
- Internet connection (for Google Translate and gTTS)

## Installation

### macOS

```bash
# Install Python (if not installed)
brew install python

# Install ffmpeg and rubberband (for speed control)
brew install ffmpeg rubberband

# Clone repository
git clone https://github.com/smoreg/biLangGen.git
cd biLangGen

# Install Python dependencies
pip3 install -r requirements.txt
```

### Windows

```powershell
# 1. Install Python from https://python.org/downloads
#    Check "Add Python to PATH" during installation!

# 2. Install ffmpeg using Chocolatey (run PowerShell as Admin):
choco install ffmpeg

# OR using Scoop:
scoop install ffmpeg

# OR download manually from https://ffmpeg.org/download.html
# and add to PATH

# 3. Clone repository
git clone https://github.com/smoreg/biLangGen.git
cd biLangGen

# 4. Install Python dependencies
pip install -r requirements.txt
```

### Linux (Ubuntu/Debian)

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip ffmpeg rubberband-cli

# Clone repository
git clone https://github.com/smoreg/biLangGen.git
cd biLangGen

# Install Python dependencies
pip3 install -r requirements.txt
```

## Quick Start

1. Create a text file `book.txt` with your text (UTF-8 encoding)

2. Run the generator:
```bash
# macOS/Linux
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es

# Windows
python main.py -i book.txt -o audiobook.mp3 -s ru -t es
```

3. Open `audiobook.mp3` and enjoy!

## Usage Examples

### Audio Generation

```bash
# Basic: Russian → Spanish
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es

# With speed adjustment (1.5x for Russian, 1x for Spanish)
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --speed "ru:1.5,es:1.0"

# Multiple target languages (Russian → English, Spanish)
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t en,es

# Custom pauses (longer pauses)
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --pause 800 --sentence-pause 1200

# Use DeepL for better translation quality
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --translator deepl-free

# Offline TTS (no internet required for audio, but still needs internet for translation)
python3 main.py -i book.txt -o audiobook.mp3 -s ru -t es --tts pyttsx3
```

### Video Generation

```bash
# Basic video: Russian → Spanish with karaoke subtitles
python3 video_main.py -i book.txt -o video.mp4 -s ru -t es

# With AI-generated background (creates image from text content)
python3 video_main.py -i book.txt -o video.mp4 -s ru -t es --background generate

# With custom background image
python3 video_main.py -i book.txt -o video.mp4 -s ru -t es --background-image my_bg.jpg

# Custom resolution and font size
python3 video_main.py -i book.txt -o video.mp4 -s ru -t es --resolution 1280x720 --font-size 56

# More rare words displayed (up to 3)
python3 video_main.py -i book.txt -o video.mp4 -s ru -t es --rare-words 3

# Full HD with higher FPS
python3 video_main.py -i book.txt -o video.mp4 -s ru -t es --resolution 1920x1080 --fps 30
```

## CLI Options

### Audio (main.py)

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

### Video (video_main.py)

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input text file | Required |
| `-o, --output` | Output MP4 file | Required |
| `-s, --source-lang` | Source language (ru/en/es) | ru |
| `-t, --target-langs` | Target languages (comma-separated) | en |
| `--translator` | google / deepl-free / deepl-pro | google |
| `--tts` | gtts / pyttsx3 | gtts |
| `--pause` | Pause between languages (ms) | 500 |
| `--sentence-pause` | Pause between sentences (ms) | 800 |
| `--speed` | Speed per language, e.g. "ru:2.0,es:1.0" | 1.0 |
| `--background` | Background color (hex) or "generate" for AI | #000000 |
| `--background-image` | Custom background image path | None |
| `--font-size` | Subtitle font size | 48 |
| `--resolution` | Video resolution (e.g. 1920x1080) | 1920x1080 |
| `--rare-words` | Max rare words per sentence (1-3) | 3 |
| `--fps` | Video frames per second | 24 |

## Providers

### Translation
| Provider | Quality | Free Limit | Best For |
|----------|---------|------------|----------|
| **Google** (default) | Good | Unlimited* | Daily use |
| **DeepL Free** | Excellent | 500K chars/month | Best quality |
| **DeepL Pro** | Excellent | Paid | Large volumes |

*Google through unofficial API may have rate limits

### TTS (Text-to-Speech)
| Provider | Quality | Internet | Best For |
|----------|---------|----------|----------|
| **gTTS** (default) | Good | Required | Most cases |
| **pyttsx3** | Basic | Not required | Offline use |

## Rate Limiting

Built-in protection against API blocks:
- Adaptive rate limiting (speeds up on success, slows down on errors)
- Exponential backoff retries (up to 5 attempts)
- Preventive pauses every 100 requests
- Translation caching to reduce API calls

### Recommended limits
| Text Size | Status |
|-----------|--------|
| Short story (5-10 pages) | Works great |
| Novel (50-100 pages) | Should work, takes 10-30 min |
| Long book (300+ pages) | Split into parts recommended |

## Troubleshooting

### "ffmpeg not found"
Make sure ffmpeg is installed and in your PATH:
```bash
ffmpeg -version
```

### Speed control not working
Install rubberband:
- macOS: `brew install rubberband`
- Linux: `sudo apt install rubberband-cli`
- Windows: Speed control uses ffmpeg (already installed)

### Rate limit errors
The tool will automatically retry with backoff. For large texts, consider:
- Using `--translator deepl-free` (500K chars/month free)
- Splitting text into smaller files
- Running during off-peak hours

## Project Structure

```
biLangGen/
├── main.py              # Audio CLI entry point
├── video_main.py        # Video CLI entry point
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
├── video/
│   ├── generator.py     # Main video generator
│   ├── karaoke.py       # Karaoke subtitle rendering
│   ├── word_cards.py    # Rare word cards display
│   ├── backgrounds.py   # Background rendering
│   └── image_gen.py     # AI background generation
├── analysis/
│   └── word_frequency.py # Word rarity analysis
├── utils/
│   └── rate_limiter.py  # Rate limiting utilities
└── requirements.txt
```

## License

MIT
