#!/bin/bash
# Batch process 20 Sheckley stories to es-latam
# Settings: ru -> es-latam, speeds 1.5/0.8, Gemini translator, wordcard audio enabled
# Gemini quota: ~560 requests needed, 1500/day available - OK!

set -e
cd "$(dirname "$0")/.."

# Load API keys from .env
if [[ -f .env ]]; then
    export $(cat .env | xargs)
fi

# Stories to process (have images, not yet processed)
STORIES=(
    "Абсолютное оружие"
    "Билет на планету Транай"
    "Верный вопрос"
    "Вор во времени"
    "Академия"
    "Безымянная гора"
    "Беличье колесо"
    "Бесконечный вестерн"
    "Болото"
    "Бремя человека"
    "Возвращение человека"
    "Второй рай"
    "Вымогатель"
    "Глаз реальности"
    "Глубокий Синий сон"
    "Голоса"
    "Девушки и Наджент Миллер"
    "Дипломатическая неприкосновенность"
    "Долой паразитов!"
    "Жертва из космоса"
)

SOURCE_DIR="txt_source/sheckley/рассказы"

echo "=== Batch Sheckley Stories Processing ==="
echo "Total stories: ${#STORIES[@]}"
echo "Translator: openai"
echo ""

# Limit: process only first N stories (set to 0 for all)
LIMIT=2
COUNT=0

for story in "${STORIES[@]}"; do
    # Check limit
    if [[ $LIMIT -gt 0 && $COUNT -ge $LIMIT ]]; then
        echo "LIMIT reached ($LIMIT stories), stopping."
        break
    fi
    COUNT=$((COUNT + 1))
    txt_file="$SOURCE_DIR/${story}.txt"

    # Find image (png, jpg, or jpeg)
    img_file=""
    for ext in png jpg jpeg; do
        if [[ -f "$SOURCE_DIR/${story}.$ext" ]]; then
            img_file="$SOURCE_DIR/${story}.$ext"
            break
        fi
    done

    if [[ ! -f "$txt_file" ]]; then
        echo "SKIP: $story - txt not found"
        continue
    fi

    if [[ -z "$img_file" ]]; then
        echo "SKIP: $story - image not found"
        continue
    fi

    # Alternate translators: odd=openai, even=gemini
    if (( COUNT % 2 == 1 )); then
        TRANSLATOR="openai"
    else
        TRANSLATOR="gemini"
    fi

    echo "Processing: $story"
    echo "  Text: $txt_file"
    echo "  Image: $img_file"
    echo "  Translator: $TRANSLATOR"

    python3 main.py run \
        -i "$txt_file" \
        -s ru -t es-latam \
        --translator "$TRANSLATOR" \
        --translator-parallel 4 \
        --tts google_cloud \
        --tts-parallel 4 \
        --tts-target-locale es-latam \
        --combine-workers 8 \
        --video-workers 8 \
        --speed-source 1.5 \
        --speed-target 0.8 \
        --enable-wordcard-audio \
        --background "$img_file"

    echo "Completed: $story"
    echo "---"
done

echo ""
echo "=== All done! ==="
