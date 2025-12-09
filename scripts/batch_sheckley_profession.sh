#!/bin/bash
# Batch script for 4 audiobooks:
# - asimov_profession (Азимов - Профессия)
# - 3 Sheckley stories (Шекли)
#
# Run: ./scripts/batch_sheckley_profession.sh

set -e
cd "$(dirname "$0")/.."

echo "=========================================="
echo "Batch: 4 Audiobooks (Profession + Sheckley)"
echo "=========================================="

# Define books: NAME|INPUT_FILE|IMAGE_FILE
declare -a BOOKS=(
    "asimov_profession|txt_source/asimov_profession.txt|txt_source/asimov_profession.png"
    "Билет на планету Транай|txt_source/sheckley/рассказы/Билет на планету Транай.txt|txt_source/sheckley/рассказы/Билет на планету Транай.png"
    "Абсолютное оружие|txt_source/sheckley/рассказы/Абсолютное оружие.txt|txt_source/sheckley/рассказы/Абсолютное оружие.png"
    "Верный вопрос|txt_source/sheckley/рассказы/Верный вопрос.txt|txt_source/sheckley/рассказы/Верный вопрос.png"
)

TOTAL=${#BOOKS[@]}
CURRENT=0

for BOOK_INFO in "${BOOKS[@]}"; do
    IFS='|' read -r BOOK_NAME INPUT_FILE IMAGE_FILE <<< "$BOOK_INFO"
    CURRENT=$((CURRENT + 1))

    echo ""
    echo "=========================================="
    echo "[$CURRENT/$TOTAL] $BOOK_NAME"
    echo "=========================================="

    # Check input file
    if [ ! -f "$INPUT_FILE" ]; then
        echo "❌ Input file not found: $INPUT_FILE"
        continue
    fi

    # Calculate parallelism
    FILE_SIZE=$(wc -c < "$INPUT_FILE")
    if [ $FILE_SIZE -gt 200000 ]; then
        PARALLEL=16
    elif [ $FILE_SIZE -gt 51200 ]; then
        PARALLEL=8
    else
        PARALLEL=4
    fi

    echo "  Input: $INPUT_FILE ($(numfmt --to=iec $FILE_SIZE 2>/dev/null || echo "${FILE_SIZE}B"))"
    echo "  Parallel: $PARALLEL workers"

    # Build command
    CMD="python3 main.py run"
    CMD="$CMD -i \"$INPUT_FILE\""
    CMD="$CMD -s ru -t es"
    CMD="$CMD --translator openai"
    CMD="$CMD --translator-parallel $PARALLEL"
    CMD="$CMD --tts google_cloud"
    CMD="$CMD --tts-parallel $PARALLEL"
    CMD="$CMD --tts-target-locale es-latam"
    CMD="$CMD --combine-workers $PARALLEL"
    CMD="$CMD --video-workers 8"
    CMD="$CMD --speed-source 1.5"
    CMD="$CMD --speed-target 0.8"

    # Add background if exists
    if [ -f "$IMAGE_FILE" ]; then
        CMD="$CMD --background \"$IMAGE_FILE\""
        echo "  Background: ✓"
    else
        echo "  Background: ✗ (black)"
    fi

    echo ""
    echo "Running pipeline..."
    eval $CMD

    echo ""
    echo "✅ Completed: $BOOK_NAME"
done

echo ""
echo "=========================================="
echo "✅ All $TOTAL audiobooks completed!"
echo "=========================================="
echo ""
echo "Output videos:"
for BOOK_INFO in "${BOOKS[@]}"; do
    IFS='|' read -r BOOK_NAME INPUT_FILE IMAGE_FILE <<< "$BOOK_INFO"
    # Extract filename without extension for project name
    BASENAME=$(basename "$INPUT_FILE" .txt)
    echo "  projects/${BASENAME}_ru_es/video/output.mp4"
done
