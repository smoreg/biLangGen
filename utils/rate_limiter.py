"""Rate limiting and retry utilities."""

import random
import time
from functools import wraps
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class RateLimiter:
    """
    Adaptive rate limiter with exponential backoff.

    Automatically slows down when errors occur and speeds up
    when requests succeed.
    """

    def __init__(
        self,
        min_delay: float = 0.5,
        max_delay: float = 30.0,
        initial_delay: float = 0.5,
        backoff_factor: float = 2.0,
        recovery_factor: float = 0.9,
        jitter: float = 0.1,
    ):
        """
        Initialize rate limiter.

        Args:
            min_delay: Minimum delay between requests (seconds)
            max_delay: Maximum delay between requests (seconds)
            initial_delay: Starting delay (seconds)
            backoff_factor: Multiply delay by this on error
            recovery_factor: Multiply delay by this on success
            jitter: Random jitter factor (0.1 = ±10%)
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.current_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.jitter = jitter
        self._last_request_time: float = 0
        self._consecutive_errors: int = 0

    def wait(self) -> None:
        """Wait appropriate time before next request."""
        elapsed = time.time() - self._last_request_time
        delay = self._get_delay_with_jitter()

        if elapsed < delay:
            time.sleep(delay - elapsed)

        self._last_request_time = time.time()

    def _get_delay_with_jitter(self) -> float:
        """Get current delay with random jitter."""
        jitter_range = self.current_delay * self.jitter
        jitter = random.uniform(-jitter_range, jitter_range)
        return max(self.min_delay, self.current_delay + jitter)

    def report_success(self) -> None:
        """Report successful request - speeds up rate."""
        self._consecutive_errors = 0
        self.current_delay = max(
            self.min_delay,
            self.current_delay * self.recovery_factor
        )

    def report_error(self) -> None:
        """Report failed request - slows down rate."""
        self._consecutive_errors += 1
        self.current_delay = min(
            self.max_delay,
            self.current_delay * self.backoff_factor
        )

    def get_retry_delay(self, attempt: int) -> float:
        """Get delay before retry attempt with exponential backoff."""
        base_delay = self.current_delay * (self.backoff_factor ** attempt)
        jitter = random.uniform(0, base_delay * self.jitter)
        return min(self.max_delay, base_delay + jitter)


def retry_with_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        backoff_factor: Multiply delay by this factor each retry
        retryable_exceptions: Tuple of exceptions to retry on
        on_retry: Optional callback(exception, attempt) called before retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Last attempt failed
                        raise

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1)

                    # Add jitter to delay
                    jitter = random.uniform(0, delay * 0.1)
                    sleep_time = min(max_delay, delay + jitter)

                    time.sleep(sleep_time)
                    delay *= backoff_factor

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class BatchRateLimiter:
    """
    Rate limiter for batch operations.

    Adds longer pauses periodically to avoid detection.
    """

    def __init__(
        self,
        requests_per_batch: int = 20,
        delay_between_requests: float = 0.5,
        delay_between_batches: float = 5.0,
        long_pause_every: int = 100,
        long_pause_duration: float = 30.0,
    ):
        """
        Initialize batch rate limiter.

        Args:
            requests_per_batch: Number of requests before batch pause
            delay_between_requests: Delay between individual requests
            delay_between_batches: Longer delay after each batch
            long_pause_every: Take a long pause every N requests
            long_pause_duration: Duration of long pause
        """
        self.requests_per_batch = requests_per_batch
        self.delay_between_requests = delay_between_requests
        self.delay_between_batches = delay_between_batches
        self.long_pause_every = long_pause_every
        self.long_pause_duration = long_pause_duration
        self._request_count = 0
        self._last_request_time: float = 0

    def wait(self) -> None:
        """Wait appropriate time before next request."""
        self._request_count += 1

        # Long pause every N requests
        if self._request_count % self.long_pause_every == 0:
            print(f"    [Rate limiter] Long pause ({self.long_pause_duration}s) after {self._request_count} requests...")
            time.sleep(self.long_pause_duration)
            return

        # Batch pause
        if self._request_count % self.requests_per_batch == 0:
            time.sleep(self.delay_between_batches)
            return

        # Normal delay
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_between_requests:
            time.sleep(self.delay_between_requests - elapsed)

        self._last_request_time = time.time()
