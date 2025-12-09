"""FFmpeg-based video generator with ASS subtitles - FAST!"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from pydub import AudioSegment


@dataclass
class SubtitleEvent:
    """Single subtitle event."""
    start_ms: int
    end_ms: int
    text: str
    style: str = "Default"
    is_highlighted: bool = False


def ms_to_ass_time(ms: int) -> str:
    """Convert milliseconds to ASS time format (H:MM:SS.cc)."""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    centiseconds = (ms % 1000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


class ASSGenerator:
    """Generate ASS subtitle file with karaoke effect."""

    def __init__(
        self,
        resolution: Tuple[int, int] = (1920, 1080),
        font_size: int = 48,
        font_name: str = "Arial",
    ):
        self.width, self.height = resolution
        self.font_size = font_size
        self.font_name = font_name

    def generate_header(self) -> str:
        """Generate ASS file header with styles."""
        # Colors in ASS are in &HAABBGGRR format
        return f"""[Script Info]
Title: biLangGen Subtitles
ScriptType: v4.00+
PlayResX: {self.width}
PlayResY: {self.height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Source,{self.font_name},{self.font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,30,30,150,1
Style: SourceDim,{self.font_name},{self.font_size},&H00888888,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,30,30,150,1
Style: SourceHighlight,{self.font_name},{self.font_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,30,30,150,1
Style: Target,{self.font_name},{int(self.font_size * 0.9)},&H00AAAAAA,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,50,1
Style: TargetHighlight,{self.font_name},{int(self.font_size * 0.9)},&H0000FF00,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,1,2,30,30,50,1
Style: WordCard,{self.font_name},{int(self.font_size * 0.7)},&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,1,8,30,30,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _format_dialogue(self, text: str) -> str:
        """Format text with line breaks for dialogues."""
        import re

        # Russian dialogue uses em-dash "—"
        # Pattern 1: sentence ending + " — " + new speech (e.g., "сказал он. — Привет!")
        formatted = re.sub(r'([.!?»])\s*—\s*', r'\1\\N— ', text)

        # Pattern 2: comma + " — " + speech continuation (e.g., "крикнул, — Стой!")
        formatted = re.sub(r',\s*—\s*', r',\\N— ', formatted)

        # Spanish dialogue markers: sentence + "- " (e.g., 'dijo. - Hola')
        formatted = re.sub(r'([.!?"])\s*-\s+', r'\1\\N- ', formatted)

        return formatted

    def generate_karaoke_line(
        self,
        text: str,
        start_ms: int,
        duration_ms: int,
        style: str,
        highlight_style: str,
    ) -> str:
        """Generate karaoke effect using ASS \\k tags."""
        import re

        # Handle \N line breaks - split into segments
        segments = re.split(r'(\\N)', text)

        # Calculate total chars (excluding \N markers)
        total_chars = sum(len(s) for s in segments if s != '\\N')
        if total_chars == 0:
            total_chars = 1

        # Generate karaoke with \k tags
        karaoke_parts = []
        for segment in segments:
            if segment == '\\N':
                # Preserve line break
                karaoke_parts.append('\\N')
            else:
                # Split segment into words
                words = segment.split()
                for word in words:
                    word_duration_cs = int((len(word) / total_chars) * (duration_ms / 10))
                    karaoke_parts.append(f"{{\\k{word_duration_cs}}}{word}")

        # Join parts with spaces (but \N already included)
        karaoke_text = ""
        for i, part in enumerate(karaoke_parts):
            if part == '\\N':
                karaoke_text += part
            elif karaoke_text and not karaoke_text.endswith('\\N'):
                karaoke_text += " " + part
            else:
                karaoke_text += part

        end_ms = start_ms + duration_ms
        line = f"Dialogue: 0,{ms_to_ass_time(start_ms)},{ms_to_ass_time(end_ms)},{style},,0,0,0,,{{\\k0}}{karaoke_text}"

        return line

    def generate_subtitle_events(
        self,
        sentences_source: List[str],
        sentences_target: List[str],
        rare_words: List[List[Tuple[str, str]]],
        timeline: List[Dict[str, Any]],
    ) -> str:
        """Generate all subtitle events."""
        events = []

        for i, item in enumerate(timeline):
            start_ms = int(item["start"] * 1000)
            src_dur_ms = int(item["source_duration"] * 1000)
            tgt_dur_ms = int(item["target_duration"] * 1000)
            end_ms = int(item["end"] * 1000)

            source_text = sentences_source[i] if i < len(sentences_source) else ""
            target_text = sentences_target[i] if i < len(sentences_target) else ""
            words = rare_words[i] if i < len(rare_words) else []

            # Calculate timings based on start and durations
            # Use pause_between from timeline for accurate target start time
            pause_ms = int(item.get("pause_between", 0.5) * 1000)
            source_end_ms = start_ms + src_dur_ms
            target_start_ms = source_end_ms + pause_ms
            target_end_ms = target_start_ms + tgt_dur_ms

            # Word cards at top (visible during entire sentence) - up to 7 words
            # Display vertically, one word per line
            if words:
                word_lines = [f"{w[0]} → {w[1]}" for w in words[:7]]
                word_text = "\\N".join(word_lines)
                events.append(
                    f"Dialogue: 1,{ms_to_ass_time(start_ms)},{ms_to_ass_time(end_ms)},WordCard,,0,0,0,,{word_text}"
                )

            # Format text with line breaks for dialogues
            # Replace " — " (dialogue marker) with line break
            source_formatted = self._format_dialogue(source_text)
            target_formatted = self._format_dialogue(target_text)

            # TARGET text visible from START (dimmed initially)
            # Phase 1: Source playing - target is dim
            events.append(
                f"Dialogue: 0,{ms_to_ass_time(start_ms)},{ms_to_ass_time(target_start_ms)},Target,,0,0,0,,{target_formatted}"
            )

            # SOURCE with karaoke effect (Phase 1) - use formatted text with line breaks
            events.append(
                self.generate_karaoke_line(source_formatted, start_ms, src_dur_ms, "Source", "SourceHighlight")
            )

            # Phase 2: Pause - source highlighted, target still dim
            events.append(
                f"Dialogue: 0,{ms_to_ass_time(source_end_ms)},{ms_to_ass_time(target_start_ms)},SourceHighlight,,0,0,0,,{source_formatted}"
            )

            # Phase 3: Target playing
            # Source stays highlighted (dimmed)
            events.append(
                f"Dialogue: 0,{ms_to_ass_time(target_start_ms)},{ms_to_ass_time(end_ms)},SourceDim,,0,0,0,,{source_formatted}"
            )

            # Target with karaoke - use formatted text with line breaks
            events.append(
                self.generate_karaoke_line(target_formatted, target_start_ms, tgt_dur_ms, "Target", "TargetHighlight")
            )

        return "\n".join(events)

    def generate(
        self,
        sentences_source: List[str],
        sentences_target: List[str],
        rare_words: List[List[Tuple[str, str]]],
        timeline: List[Dict[str, Any]],
        output_path: Path,
    ) -> Path:
        """Generate complete ASS file."""
        content = self.generate_header()
        content += self.generate_subtitle_events(
            sentences_source, sentences_target, rare_words, timeline
        )

        output_path = Path(output_path)
        output_path.write_text(content, encoding="utf-8")
        return output_path


class FFmpegVideoGenerator:
    """Generate video using FFmpeg (FAST!)."""

    def __init__(
        self,
        resolution: Tuple[int, int] = (1920, 1080),
        fps: int = 24,
        font_size: int = 48,
        background_color: str = "black",
    ):
        self.width, self.height = resolution
        self.fps = fps
        self.font_size = font_size
        self.background_color = background_color
        self.ass_generator = ASSGenerator(resolution, font_size)

    def build_timeline(
        self,
        sentences_source: List[str],
        sentences_target: List[str],
        audio_duration: float,
        pause_between_langs: float = 0.5,
        pause_between_sentences: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """Build timeline with estimated durations."""
        # Estimate durations proportionally based on text length
        total_chars = sum(
            len(s) + len(t)
            for s, t in zip(sentences_source, sentences_target)
        )

        total_pauses = (
            len(sentences_source) * pause_between_langs +
            (len(sentences_source) - 1) * pause_between_sentences
        )
        audio_only_duration = audio_duration - total_pauses

        timeline = []
        current_time = 0.0

        for i, (src, tgt) in enumerate(zip(sentences_source, sentences_target)):
            sent_chars = len(src) + len(tgt)
            proportion = sent_chars / total_chars if total_chars > 0 else 1 / len(sentences_source)
            sentence_audio_duration = audio_only_duration * proportion

            src_dur = sentence_audio_duration * 0.5
            tgt_dur = sentence_audio_duration * 0.5
            sentence_duration = src_dur + pause_between_langs + tgt_dur

            timeline.append({
                "start": current_time,
                "end": current_time + sentence_duration,
                "source_duration": src_dur,
                "target_duration": tgt_dur,
                "pause_between": pause_between_langs,
            })

            current_time += sentence_duration
            if i < len(sentences_source) - 1:
                current_time += pause_between_sentences

        return timeline

    def generate(
        self,
        sentences_source: List[str],
        sentences_target: List[str],
        rare_words: List[List[Tuple[str, str]]],
        audio_path: Path,
        output_path: Path,
        subtitles_path: Path = None,
    ) -> Path:
        """Generate video with FFmpeg."""
        audio_path = Path(audio_path)
        output_path = Path(output_path)

        # Get audio duration
        audio = AudioSegment.from_file(str(audio_path))
        duration = len(audio) / 1000.0
        print(f"[FFmpeg] Audio duration: {duration:.1f}s")

        # Build timeline
        timeline = self.build_timeline(sentences_source, sentences_target, duration)

        # Generate ASS subtitles
        if subtitles_path is None:
            subtitles_path = output_path.with_suffix(".ass")

        print(f"[FFmpeg] Generating subtitles: {subtitles_path}")
        self.ass_generator.generate(
            sentences_source, sentences_target, rare_words, timeline, subtitles_path
        )

        # Generate video with FFmpeg
        print(f"[FFmpeg] Generating video: {output_path}")

        # FFmpeg command:
        # 1. Create black background video
        # 2. Add audio
        # 3. Burn in subtitles
        cmd = [
            "ffmpeg", "-y",
            # Black background
            "-f", "lavfi",
            "-i", f"color=c={self.background_color}:s={self.width}x{self.height}:r={self.fps}:d={duration}",
            # Audio
            "-i", str(audio_path),
            # Subtitle filter (burn in)
            "-vf", f"ass={subtitles_path}",
            # Output settings
            "-c:v", "libx264",
            "-preset", "fast",  # faster encoding
            "-crf", "23",       # good quality
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]

        print(f"[FFmpeg] Running: {' '.join(cmd[:10])}...")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[FFmpeg] Error: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")

        print(f"[FFmpeg] Done! Video saved to: {output_path}")
        return output_path


def generate_from_project(project_dir: Path, output_path: Path = None) -> Path:
    """Generate video from project directory."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from project import Project

    project = Project.load(project_dir)

    # Load data
    sentences = project.get_sentences()
    translations = project.get_translations()
    rare_words_data = project.get_rare_words()

    sentences_source = [s["text"] for s in sentences]
    sentences_target = [t["text"] for t in translations]
    rare_words = [r["words"] for r in rare_words_data]

    # Get audio
    audio_path = project.get_combined_audio_path()
    if not audio_path.exists():
        raise FileNotFoundError(f"Combined audio not found: {audio_path}")

    # Output path
    if output_path is None:
        output_path = project.get_output_video_path()

    # Generate
    generator = FFmpegVideoGenerator(
        resolution=(1920, 1080),
        fps=24,
        font_size=48,
    )

    subtitles_path = project.get_subtitles_path()

    return generator.generate(
        sentences_source=sentences_source,
        sentences_target=sentences_target,
        rare_words=rare_words,
        audio_path=audio_path,
        output_path=output_path,
        subtitles_path=subtitles_path,
    )


def _encode_video_chunk(args: Tuple) -> Tuple[int, Path]:
    """Encode a single video chunk. Must be at module level for multiprocessing."""
    idx, chunk_start, chunk_dur, chunk_ass, chunk_video, width, height, fps, audio_path, preset, crf, background_image = args

    if background_image:
        # Use background image with scaling/cropping and darkening
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(background_image),
            "-ss", str(chunk_start), "-t", str(chunk_dur), "-i", str(audio_path),
            "-vf", (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"eq=brightness=-0.2:saturation=0.8,"
                f"fps={fps},"
                f"ass={chunk_ass}"
            ),
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(chunk_dur),
            str(chunk_video)
        ]
    else:
        # Black background
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={chunk_dur}",
            "-ss", str(chunk_start), "-t", str(chunk_dur), "-i", str(audio_path),
            "-vf", f"ass={chunk_ass}",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(chunk_dur),
            str(chunk_video)
        ]

    subprocess.run(cmd, capture_output=True, check=True)
    return idx, Path(chunk_video)


def generate_video_parallel(
    audio_path: Path,
    ass_path: Path,
    output_path: Path,
    resolution: Tuple[int, int] = (1920, 1080),
    fps: int = 24,
    num_workers: int = 4,
    preset: str = "ultrafast",
    crf: int = 28,
    background_image: Path = None,
) -> Path:
    """Generate video using parallel chunk encoding.

    Splits video into chunks, encodes in parallel, then concatenates.
    ~4x faster than sequential encoding on 4 cores.

    Args:
        audio_path: Path to combined audio file
        ass_path: Path to ASS subtitles file
        output_path: Output video path
        resolution: Video resolution (width, height)
        fps: Frames per second
        num_workers: Number of parallel encoding workers
        preset: x264 preset (ultrafast/fast/medium)
        crf: Quality (lower = better, 18-28 typical)

    Returns:
        Path to generated video
    """
    import tempfile
    import shutil
    from concurrent.futures import ProcessPoolExecutor, as_completed

    audio_path = Path(audio_path)
    ass_path = Path(ass_path)
    output_path = Path(output_path)

    # Get audio duration
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())

    # Calculate chunk parameters
    chunk_duration = duration / num_workers
    width, height = resolution

    # Create temp directory for chunks
    temp_dir = Path(tempfile.mkdtemp(prefix="video_chunks_"))

    try:
        # Generate ASS chunks with shifted timing
        ass_chunks = []
        for i in range(num_workers):
            chunk_start = i * chunk_duration
            chunk_end = (i + 1) * chunk_duration if i < num_workers - 1 else duration

            # Create shifted ASS for this chunk
            chunk_ass = temp_dir / f"chunk_{i}.ass"
            _create_shifted_ass(ass_path, chunk_ass, chunk_start, chunk_end)
            ass_chunks.append(chunk_ass)

        # Prepare args for parallel execution
        encode_args = []
        bg_path = str(background_image) if background_image else None
        for i in range(num_workers):
            chunk_start = i * chunk_duration
            chunk_dur = chunk_duration if i < num_workers - 1 else (duration - chunk_start)
            chunk_video = temp_dir / f"chunk_{i}.mp4"
            encode_args.append((
                i, chunk_start, chunk_dur, str(ass_chunks[i]), str(chunk_video),
                width, height, fps, str(audio_path), preset, crf, bg_path
            ))

        # Run encoding in parallel with progress monitoring
        chunk_videos = []
        print(f"[video] Encoding {num_workers} chunks in parallel...")
        print(f"[video] Total duration: {duration:.1f}s ({duration/60:.1f}min)")
        if background_image:
            print(f"[video] Background image: {background_image}")

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_encode_video_chunk, args): args[0] for args in encode_args}
            completed = 0

            for future in as_completed(futures):
                idx, chunk_video = future.result()
                chunk_videos.append((idx, chunk_video))
                completed += 1

                # Show progress
                chunk_size_mb = chunk_video.stat().st_size / (1024 * 1024)
                print(f"[video] Chunk {idx + 1}/{num_workers} done ({chunk_size_mb:.1f}MB) | {completed}/{num_workers} complete")

        # Sort by index
        chunk_videos.sort(key=lambda x: x[0])

        # Create concat list
        concat_list = temp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for idx, chunk_video in chunk_videos:
                f.write(f"file '{chunk_video}'\n")

        # Concatenate chunks
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        return output_path

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def _create_shifted_ass(source_ass: Path, output_ass: Path, start_sec: float, end_sec: float):
    """Create ASS file with events shifted to start from 0 for a time window.

    Only includes events that overlap with [start_sec, end_sec] window,
    with times shifted so chunk starts at 0.
    """
    import re

    with open(source_ass, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into header and events
    parts = content.split("[Events]")
    if len(parts) != 2:
        # No events section, just copy
        with open(output_ass, "w", encoding="utf-8") as f:
            f.write(content)
        return

    header = parts[0] + "[Events]\n"
    events_section = parts[1]

    # Find Format line and dialogue lines
    lines = events_section.strip().split("\n")
    format_line = ""
    dialogues = []

    for line in lines:
        if line.startswith("Format:"):
            format_line = line
        elif line.startswith("Dialogue:"):
            dialogues.append(line)

    # Parse and filter dialogues
    shifted_dialogues = []

    def parse_ass_time(time_str: str) -> float:
        """Parse ASS time (H:MM:SS.cc) to seconds."""
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s

    def format_ass_time(seconds: float) -> str:
        """Format seconds to ASS time (H:MM:SS.cc)."""
        if seconds < 0:
            seconds = 0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    for dialogue in dialogues:
        # Parse dialogue: Dialogue: Layer,Start,End,Style,...
        match = re.match(r"Dialogue:\s*(\d+),([^,]+),([^,]+),(.+)", dialogue)
        if not match:
            continue

        layer = match.group(1)
        start_time = parse_ass_time(match.group(2))
        end_time = parse_ass_time(match.group(3))
        rest = match.group(4)

        # Check if event overlaps with our window
        if end_time <= start_sec or start_time >= end_sec:
            continue  # No overlap

        # Shift times relative to chunk start
        new_start = max(0, start_time - start_sec)
        new_end = min(end_sec - start_sec, end_time - start_sec)

        shifted_dialogue = f"Dialogue: {layer},{format_ass_time(new_start)},{format_ass_time(new_end)},{rest}"
        shifted_dialogues.append(shifted_dialogue)

    # Write output
    with open(output_ass, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(format_line + "\n")
        f.write("\n".join(shifted_dialogues))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        project_dir = Path(sys.argv[1])
    else:
        project_dir = Path(__file__).parent.parent / "projects" / "strazh_pticy_ru_es"

    generate_from_project(project_dir)
