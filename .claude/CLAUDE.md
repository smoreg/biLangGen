# CLAUDE.md

biLangGen — генератор двуязычных аудиокниг/видео. Текст → предложения → перевод → редкие слова → TTS → видео с караоке-субтитрами.

## Commands

```bash
# ═══════════════════════════════════════════════════════════════════
# RECOMMENDED DEFAULTS (copy-paste ready)
# ═══════════════════════════════════════════════════════════════════

# ru → es-latam (per_word mode, Google Cloud TTS for Spanish)
python3 main.py run -i txt_source/BOOK.txt -s ru -t es-latam \
  --translator openai --translator-parallel 4 \
  --tts-source openai --tts-target google_cloud --tts-parallel 4 \
  --tts-wordcards-target google_cloud --tts-wordcards-source google_cloud \
  --tts-target-locale es-latam \
  --enable-wordcard-audio --wordcard-mode per_word \
  --combine-workers 8 --video-workers 4 \
  --background samename

# ru → en (combined mode, all OpenAI TTS)
python3 main.py run -i txt_source/BOOK.txt -s ru -t en \
  --translator openai --translator-parallel 4 \
  --tts openai --tts-parallel 4 \
  --enable-wordcard-audio --wordcard-mode combined \
  --combine-workers 8 --video-workers 4 \
  --background samename

# ═══════════════════════════════════════════════════════════════════
# OTHER COMMANDS
# ═══════════════════════════════════════════════════════════════════

# Resume interrupted project
python3 main.py resume PROJECT_NAME

# List all projects
python3 main.py list

# Check quota usage
python3 main.py quota
```

### Options Reference

| Option | Description |
|--------|-------------|
| `--translator openai` | GPT-4o-mini translation (best for es-latam) |
| `--translator-parallel 4` | 4 parallel translation threads |
| `--tts-source openai` | TTS for source language (ru) |
| `--tts-target google_cloud` | TTS for target language |
| `--tts-parallel 4` | 4 parallel TTS threads |
| `--tts-target-locale es-latam` | Latin American Spanish accent |
| `--wordcard-mode combined` | One TTS per wordcard (OpenAI) |
| `--wordcard-mode per_word` | Separate TTS per word (Google Cloud) |
| `--tts-wordcards-target` | TTS for target words in per_word mode |
| `--tts-wordcards-source` | TTS for source translations in per_word mode |
| `--combine-workers 8` | 8 parallel audio combine threads |
| `--video-workers 4` | 4 parallel video encoding threads |
| `--background samename` | Find image with same name as input file |

## YouTube Upload

```bash
# Preview metadata (dry run)
python3 scripts/youtube_upload.py "Project_ru_es-latam" --dry-run

# Upload (private by default)
python3 scripts/youtube_upload.py "Project_ru_es-latam"

# Upload as public
python3 scripts/youtube_upload.py "Project_ru_es-latam" --privacy public
```

Requires `client_secrets.json` (OAuth 2.0 Desktop app from Google Cloud Console with YouTube Data API v3).

## Project Structure

```
projects/{name}_{source}_{target}/
├── project.db              # SQLite (sentences, translations, rare_words, progress)
├── text/original.txt       # Source text
├── audio/
│   ├── source/*.mp3        # TTS source language
│   ├── target/*.mp3        # TTS target language
│   ├── wordcards/*.mp3     # TTS word cards
│   ├── combined.mp3        # Final audio
│   └── timeline.json       # Timing data
└── video/
    ├── background.png      # Background image
    ├── subtitles.ass       # ASS subtitles
    └── output.mp4          # Final video
```

### Pipeline Steps

1. `sentences` — NLTK tokenization
2. `translation` — OpenAI/Argos/DeepL
3. `rare_words_extract` — Zipf frequency scoring
4. `rare_words_translate` — OpenAI word translations
5. `audio_source` — TTS source language
6. `audio_target` — TTS target language
7. `audio_wordcards` — TTS word cards
8. `audio_combined` — ffmpeg concat
9. `video` — ASS subtitles + ffmpeg encoding

## Language Codes

| Code | Language | Notes |
|------|----------|-------|
| `es-latam` | Argentine Spanish | vos/ustedes, латиноамериканский акцент |
| `es` | European Spanish | tú/vosotros, испанский акцент |
| `en` | English | |
| `ru` | Russian | |

## External Dependencies

- **ffmpeg** — required
- **Google Cloud TTS** — ADC from `~/.config/gcloud/application_default_credentials.json`
- **OpenAI API** — `OPENAI_API_KEY` env variable
