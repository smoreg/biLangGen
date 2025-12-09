#!/bin/bash
# Test script for OpenAI LATAM audiobook pipeline
# Uses borges_ragnarek.txt (5KB) - small file with existing image

set -e

cd "$(dirname "$0")/.."

# Configuration
BOOK_NAME="borges_ragnarek"
INPUT_FILE="txt_source/${BOOK_NAME}.txt"
IMAGE_FILE="txt_source/${BOOK_NAME}.png"
PROJECT_NAME="${BOOK_NAME}_ru_es"
PROJECT_DIR="projects/${PROJECT_NAME}"

echo "=========================================="
echo "Test: OpenAI LATAM Audiobook Pipeline"
echo "Book: ${BOOK_NAME}"
echo "=========================================="

# Step 0: Clean up existing test project
if [ -d "$PROJECT_DIR" ]; then
    echo "[0/4] Removing existing project..."
    rm -rf "$PROJECT_DIR"
    echo "✅ Removed: $PROJECT_DIR"
fi

# Step 1: Check prerequisites
echo "[1/4] Checking prerequisites..."

if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Input file not found: $INPUT_FILE"
    exit 1
fi
echo "  ✓ Input file: $(wc -c < "$INPUT_FILE") bytes"

if [ ! -f "$IMAGE_FILE" ]; then
    echo "⚠️  Image file not found: $IMAGE_FILE (will use black background)"
else
    echo "  ✓ Image file: $(du -h "$IMAGE_FILE" | cut -f1)"
fi

# Step 2: Set parallelism based on file size
FILE_SIZE=$(wc -c < "$INPUT_FILE")
if [ $FILE_SIZE -gt 51200 ]; then
    PARALLEL=16
else
    PARALLEL=4
fi
echo "  ✓ Parallelism: $PARALLEL (file size: $FILE_SIZE bytes)"

# Step 3: Run pipeline with background image
echo "[3/4] Running translation pipeline..."

# Build command with optional background
CMD="python3 main.py run \
    -i $INPUT_FILE \
    -s ru -t es \
    --translator openai \
    --translator-parallel $PARALLEL \
    --tts google_cloud \
    --tts-parallel $PARALLEL \
    --tts-target-locale es-latam \
    --combine-workers $PARALLEL \
    --video-workers 8 \
    --speed-source 1.5 \
    --speed-target 0.8"

# Add background if exists
if [ -f "$IMAGE_FILE" ]; then
    CMD="$CMD --background $IMAGE_FILE"
    echo "  ✓ Using background: $IMAGE_FILE"
fi

# Execute
eval $CMD

# Step 4: Check results
echo "[4/4] Checking results..."

if [ -f "$PROJECT_DIR/video/output.mp4" ]; then
    VIDEO_SIZE=$(du -h "$PROJECT_DIR/video/output.mp4" | cut -f1)
    echo "✅ Video created: $PROJECT_DIR/video/output.mp4 ($VIDEO_SIZE)"
else
    echo "❌ Video not found"
    exit 1
fi

if [ -f "$PROJECT_DIR/audio/combined.mp3" ]; then
    AUDIO_SIZE=$(du -h "$PROJECT_DIR/audio/combined.mp3" | cut -f1)
    echo "✅ Audio created: $PROJECT_DIR/audio/combined.mp3 ($AUDIO_SIZE)"
fi

echo ""
echo "=========================================="
echo "✅ Test completed successfully!"
echo "=========================================="
echo ""
echo "Output:"
echo "  Video: $PROJECT_DIR/video/output.mp4"
echo "  Audio: $PROJECT_DIR/audio/combined.mp3"
