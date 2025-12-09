"""Google Text-to-Speech provider using gTTS with rate limiting and retries."""

import time
from pathlib import Path

from gtts import gTTS
from gtts.tts import gTTSError

from core.tts_engine import BaseTTS
from core.languages import RUSSIAN, ENGLISH, SPANISH, SPANISH_LATAM, get_language
from utils.rate_limiter import RateLimiter


# gTTS language mapping (gTTS uses base language codes)
GTTS_LANG_MAP = {
    RUSSIAN.code: "ru",
    ENGLISH.code: "en",
    SPANISH.code: "es",
    SPANISH_LATAM.code: "es",  # gTTS doesn't distinguish LatAm
}


class GTTSProvider(BaseTTS):
    """
    Google TTS using gTTS library (free, online).

    Features:
    - Adaptive rate limiting
    - Exponential backoff retries
    - Periodic pauses for large batches
    """

    def __init__(
        self,
        min_delay: float = 0.3,
        max_delay: float = 30.0,
        max_retries: int = 5,
    ):
        """
        Initialize TTS provider.

        Args:
            min_delay: Minimum delay between requests
            max_delay: Maximum delay on backoff
            max_retries: Maximum retry attempts
        """
        self._rate_limiter = RateLimiter(
            min_delay=min_delay,
            max_delay=max_delay,
            initial_delay=0.3,
            backoff_factor=2.0,
            recovery_factor=0.95,
        )
        self._max_retries = max_retries
        self._request_count = 0
        self._error_count = 0

    def name(self) -> str:
        return "Google TTS (gTTS)"

    def supported_languages(self) -> list[str]:
        return list(GTTS_LANG_MAP.keys())

    def synthesize(self, text: str, language: str, output_path: str) -> bool:
        """
        Synthesize speech using gTTS with rate limiting and retries.

        Args:
            text: Text to synthesize
            language: Language code
            output_path: Path to save audio file

        Returns:
            True if successful
        """
        if not text.strip():
            return False

        self._request_count += 1

        # Status for large batches
        if self._request_count % 50 == 0:
            print(f"    [gTTS] Generated {self._request_count} audio files...")

        # Preventive pause every 100 requests
        if self._request_count % 100 == 0:
            pause_time = 8 + (self._error_count * 3)
            print(f"    [gTTS] Preventive pause ({pause_time}s) after {self._request_count} requests...")
            time.sleep(pause_time)

        return self._synthesize_with_retry(text, language, output_path)

    def _synthesize_with_retry(self, text: str, language: str, output_path: str) -> bool:
        """Execute synthesis with retry logic."""
        lang_code = GTTS_LANG_MAP.get(language, language)

        for attempt in range(self._max_retries + 1):
            try:
                # Wait according to rate limiter
                self._rate_limiter.wait()

                # Ensure directory exists
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                # Attempt synthesis
                tts = gTTS(text=text, lang=lang_code, slow=False)
                tts.save(output_path)

                # Success
                self._rate_limiter.report_success()
                return True

            except gTTSError as e:
                self._error_count += 1
                self._rate_limiter.report_error()

                error_str = str(e).lower()

                # Check if it's a rate limit error
                if "429" in error_str or "too many" in error_str:
                    self._rate_limiter.report_error()  # Extra penalty

                    if attempt < self._max_retries:
                        delay = self._rate_limiter.get_retry_delay(attempt) * 2
                        print(f"    [gTTS] Rate limited! Waiting {delay:.1f}s before retry {attempt + 1}...")
                        time.sleep(delay)
                        continue

                elif attempt < self._max_retries:
                    delay = self._rate_limiter.get_retry_delay(attempt)
                    print(f"    [gTTS] Retry {attempt + 1}/{self._max_retries} after error: {e}")
                    time.sleep(delay)
                    continue

                print(f"    [gTTS] Failed after {attempt + 1} attempts: {e}")
                return False

            except (ConnectionError, TimeoutError, OSError) as e:
                self._error_count += 1
                self._rate_limiter.report_error()

                if attempt < self._max_retries:
                    delay = self._rate_limiter.get_retry_delay(attempt)
                    print(f"    [gTTS] Connection error, retry {attempt + 1}/{self._max_retries}...")
                    time.sleep(delay)
                    continue

                print(f"    [gTTS] Connection failed: {e}")
                return False

            except Exception as e:
                print(f"    [gTTS] Unexpected error: {e}")
                return False

        return False
