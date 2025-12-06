"""Google Translate provider using deep-translator with rate limiting and retries."""

import time
from typing import Optional

from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
    RequestError,
    TooManyRequests,
    TranslationNotFound,
)

from core.translator import BaseTranslator
from utils.rate_limiter import RateLimiter, retry_with_backoff


# Exceptions that are worth retrying
RETRYABLE_EXCEPTIONS = (
    RequestError,
    TooManyRequests,
    ConnectionError,
    TimeoutError,
    OSError,
)


class GoogleFreeTranslator(BaseTranslator):
    """
    Free Google Translate using deep-translator library.

    Features:
    - Adaptive rate limiting (slows down on errors, speeds up on success)
    - Exponential backoff retries
    - Batch operation support with periodic long pauses
    """

    def __init__(
        self,
        min_delay: float = 0.3,
        max_delay: float = 30.0,
        max_retries: int = 5,
    ):
        """
        Initialize translator.

        Args:
            min_delay: Minimum delay between requests (seconds)
            max_delay: Maximum delay on backoff (seconds)
            max_retries: Maximum retry attempts per request
        """
        self._rate_limiter = RateLimiter(
            min_delay=min_delay,
            max_delay=max_delay,
            initial_delay=0.5,
            backoff_factor=2.0,
            recovery_factor=0.95,
        )
        self._max_retries = max_retries
        self._request_count = 0
        self._error_count = 0

    def name(self) -> str:
        return "Google Translate (Free)"

    def _log_retry(self, exception: Exception, attempt: int) -> None:
        """Log retry attempt."""
        print(f"    [Google] Retry {attempt}/{self._max_retries} after error: {type(exception).__name__}")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate using Google Translate with rate limiting and retries.

        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Translated text
        """
        if not text.strip():
            return text

        if source_lang == target_lang:
            return text

        self._request_count += 1

        # Periodic status for large batches
        if self._request_count % 50 == 0:
            print(f"    [Google] Processed {self._request_count} translations...")

        # Long pause every 100 requests to avoid blocks
        if self._request_count % 100 == 0:
            pause_time = 10 + (self._error_count * 5)  # Longer pause if there were errors
            print(f"    [Google] Preventive pause ({pause_time}s) after {self._request_count} requests...")
            time.sleep(pause_time)

        return self._translate_with_retry(text, source_lang, target_lang)

    def _translate_with_retry(self, text: str, source_lang: str, target_lang: str) -> str:
        """Execute translation with retry logic."""
        last_exception = None

        for attempt in range(self._max_retries + 1):
            try:
                # Wait according to rate limiter
                self._rate_limiter.wait()

                # Attempt translation
                translator = GoogleTranslator(source=source_lang, target=target_lang)
                result = translator.translate(text)

                # Success - speed up rate limiter
                self._rate_limiter.report_success()

                return result if result else text

            except TooManyRequests as e:
                # Rate limited - significant backoff
                last_exception = e
                self._error_count += 1
                self._rate_limiter.report_error()
                self._rate_limiter.report_error()  # Double penalty for rate limit

                if attempt < self._max_retries:
                    delay = self._rate_limiter.get_retry_delay(attempt) * 2
                    print(f"    [Google] Rate limited! Waiting {delay:.1f}s before retry {attempt + 1}...")
                    time.sleep(delay)

            except RETRYABLE_EXCEPTIONS as e:
                # Other retryable error
                last_exception = e
                self._error_count += 1
                self._rate_limiter.report_error()

                if attempt < self._max_retries:
                    delay = self._rate_limiter.get_retry_delay(attempt)
                    self._log_retry(e, attempt + 1)
                    time.sleep(delay)

            except Exception as e:
                # Non-retryable error
                print(f"    [Google] Non-retryable error: {e}")
                return text

        # All retries exhausted
        print(f"    [Google] All retries failed for: {text[:50]}...")
        return text  # Return original text as fallback
