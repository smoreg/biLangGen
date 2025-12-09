"""Audio file validation utilities.

Validates audio files after TTS generation to catch corrupted or empty files early.
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple


class AudioValidationError(Exception):
    """Raised when audio validation fails."""
    pass


def validate_audio_file(file_path: Path, min_duration: float = 0.1) -> Tuple[bool, Optional[str]]:
    """Validate an audio file.

    Checks:
    - File exists and has size > 0
    - File can be read by ffprobe
    - Duration is greater than min_duration

    Args:
        file_path: Path to audio file
        min_duration: Minimum duration in seconds (default 0.1s)

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, "error description")
    """
    path = Path(file_path)

    # Check file exists
    if not path.exists():
        return False, f"File does not exist: {path}"

    # Check file size
    size = path.stat().st_size
    if size == 0:
        return False, f"File is empty (0 bytes): {path}"

    if size < 100:  # Minimum reasonable size for audio
        return False, f"File too small ({size} bytes): {path}"

    # Check with ffprobe
    try:
        duration = get_audio_duration(path)
        if duration is None:
            return False, f"Could not read audio duration: {path}"

        if duration < min_duration:
            return False, f"Audio too short ({duration:.3f}s < {min_duration}s): {path}"

        return True, None

    except Exception as e:
        return False, f"Audio validation error: {e}"


def get_audio_duration(file_path: Path) -> Optional[float]:
    """Get audio file duration using ffprobe.

    Args:
        file_path: Path to audio file

    Returns:
        Duration in seconds, or None if cannot be determined
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None

        duration_str = result.stdout.strip()
        if not duration_str:
            return None

        return float(duration_str)

    except (subprocess.TimeoutExpired, ValueError, Exception):
        return None


def validate_audio_with_pydub(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate audio file using pydub (alternative method).

    Args:
        file_path: Path to audio file

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(file_path))

        if len(audio) < 100:  # Less than 100ms
            return False, f"Audio too short ({len(audio)}ms)"

        return True, None

    except Exception as e:
        return False, f"Pydub validation error: {e}"


class AudioValidator:
    """Batch audio validator with retry tracking."""

    def __init__(self, min_duration: float = 0.1, max_retries: int = 3):
        """
        Initialize validator.

        Args:
            min_duration: Minimum audio duration in seconds
            max_retries: Maximum retries for failed files
        """
        self.min_duration = min_duration
        self.max_retries = max_retries
        self._retry_counts: dict[str, int] = {}
        self._failed_files: list[str] = []

    def validate(self, file_path: Path) -> bool:
        """Validate audio file.

        Args:
            file_path: Path to audio file

        Returns:
            True if valid, False if invalid
        """
        is_valid, error = validate_audio_file(file_path, self.min_duration)

        if not is_valid:
            file_key = str(file_path)
            self._retry_counts[file_key] = self._retry_counts.get(file_key, 0) + 1

            if self._retry_counts[file_key] >= self.max_retries:
                self._failed_files.append(file_key)

        return is_valid

    def should_retry(self, file_path: Path) -> bool:
        """Check if file should be retried.

        Args:
            file_path: Path to audio file

        Returns:
            True if retries remaining, False if max retries exceeded
        """
        file_key = str(file_path)
        return self._retry_counts.get(file_key, 0) < self.max_retries

    def get_retry_count(self, file_path: Path) -> int:
        """Get retry count for a file."""
        return self._retry_counts.get(str(file_path), 0)

    @property
    def failed_files(self) -> list[str]:
        """Get list of files that failed after max retries."""
        return self._failed_files.copy()

    def reset(self):
        """Reset retry tracking."""
        self._retry_counts.clear()
        self._failed_files.clear()
