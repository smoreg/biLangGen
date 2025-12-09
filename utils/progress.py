"""Progress tracking with ETA calculation."""

import time
from collections import deque
from typing import Optional, Callable


class ProgressTracker:
    """Tracks progress with speed and ETA calculation.

    Uses sliding window average for smooth ETA estimates.
    """

    def __init__(self, total: int, window_size: int = 10, step_name: str = ""):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            window_size: Number of recent times to average for ETA
            step_name: Name of the current step (for display)
        """
        self.total = total
        self.done = 0
        self.step_name = step_name
        self.window_size = window_size

        self._start_time: Optional[float] = None
        self._last_time: Optional[float] = None
        self._times: deque = deque(maxlen=window_size)

    def start(self):
        """Mark the start of processing."""
        self._start_time = time.time()
        self._last_time = self._start_time

    def tick(self, count: int = 1):
        """Record completion of item(s).

        Args:
            count: Number of items completed (default 1)
        """
        now = time.time()

        if self._last_time is not None:
            elapsed = now - self._last_time
            # Record time per item
            if count > 0:
                self._times.append(elapsed / count)

        self._last_time = now
        self.done += count

    @property
    def percent(self) -> float:
        """Get completion percentage."""
        if self.total == 0:
            return 100.0
        return (self.done / self.total) * 100

    @property
    def items_per_second(self) -> float:
        """Get current processing speed (items/sec)."""
        if not self._times:
            return 0.0
        avg_time = sum(self._times) / len(self._times)
        if avg_time == 0:
            return 0.0
        return 1.0 / avg_time

    @property
    def eta_seconds(self) -> Optional[float]:
        """Get estimated time remaining in seconds."""
        if not self._times or self.done >= self.total:
            return None

        remaining = self.total - self.done
        avg_time = sum(self._times) / len(self._times)
        return remaining * avg_time

    @property
    def elapsed_seconds(self) -> float:
        """Get total elapsed time in seconds."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        eta = self.eta_seconds
        if eta is None:
            return "N/A"
        return format_duration(eta)

    def format_elapsed(self) -> str:
        """Format elapsed time as human-readable string."""
        return format_duration(self.elapsed_seconds)

    def format_progress(self) -> str:
        """Format full progress string for display.

        Format: [step_name] done/total (percent%) | speed items/sec | ETA: time
        """
        parts = []

        if self.step_name:
            parts.append(f"[{self.step_name}]")

        parts.append(f"{self.done}/{self.total}")
        parts.append(f"({self.percent:.0f}%)")

        speed = self.items_per_second
        if speed > 0:
            parts.append(f"| {speed:.1f} items/sec")

        eta = self.format_eta()
        if eta != "N/A":
            parts.append(f"| ETA: {eta}")

        return " ".join(parts)

    def __str__(self) -> str:
        return self.format_progress()


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "1h 23m 45s" or "45s"
    """
    if seconds < 0:
        return "N/A"

    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    seconds = seconds % 60

    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours = minutes // 60
    minutes = minutes % 60

    return f"{hours}h {minutes}m {seconds}s"


class ProgressCallback:
    """Wrapper to create progress callback for Pipeline.

    Prints progress updates to console.
    """

    def __init__(self, print_interval: int = 10):
        """
        Args:
            print_interval: Print progress every N items (0 = every item)
        """
        self.print_interval = print_interval
        self._trackers: dict[str, ProgressTracker] = {}
        self._last_printed: dict[str, int] = {}

    def __call__(self, step_name: str, done: int, total: int):
        """Progress callback compatible with Pipeline.run().

        Args:
            step_name: Current pipeline step name
            done: Number of items completed
            total: Total number of items
        """
        # Get or create tracker for this step
        if step_name not in self._trackers or self._trackers[step_name].total != total:
            self._trackers[step_name] = ProgressTracker(total, step_name=step_name)
            self._trackers[step_name].start()
            self._last_printed[step_name] = 0

        tracker = self._trackers[step_name]

        # Update tracker
        increment = done - tracker.done
        if increment > 0:
            tracker.tick(increment)

        # Print progress
        should_print = (
            self.print_interval == 0 or
            done == total or
            done - self._last_printed[step_name] >= self.print_interval
        )

        if should_print:
            print(f"\r{tracker.format_progress()}", end="", flush=True)
            self._last_printed[step_name] = done

            # Print newline when step is complete
            if done == total:
                print()


def create_progress_callback(print_every: int = 10) -> Callable[[str, int, int], None]:
    """Create a progress callback for Pipeline.

    Args:
        print_every: Print progress every N items

    Returns:
        Callback function for Pipeline.run(on_progress=...)
    """
    return ProgressCallback(print_interval=print_every)
