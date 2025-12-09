"""Google Gemini translation provider with batching and parallelization.

Features:
- Batching: Multiple sentences per request (15 sentences = 100 requests for 1500 sentences)
- Parallelization: Concurrent requests for speed (limited by 15 RPM free tier)
- Argentine Spanish (Rioplatense): voseo, local vocabulary
- Free tier: 15 RPM, 1M TPM, 1500 req/day (Gemini 1.5 Flash)
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from core.translator import BaseTranslator


# Rate limit handling constants
MAX_RETRIES = 5
BASE_DELAY = 4.0  # Base delay in seconds (Gemini free tier is slow)
MAX_DELAY = 60.0  # Maximum delay between retries

# Gemini Flash free tier limits:
# - 15 RPM (requests per minute)
# - 1M TPM (tokens per minute)
# - 1500 RPD (requests per day)
# With batch_size=15, 1500 sentences = 100 requests = well under daily limit
MAX_SAFE_WORKERS = 2  # Conservative for free tier (15 RPM / 60 * 8 = 2)
THROTTLE_DELAY = 4.0  # Delay between requests (60/15 = 4 seconds per request)


# System prompt for Argentine Spanish (same as OpenAI)
SYSTEM_PROMPT_LATAM = """You are an expert translator specializing in Russian to Argentine Spanish (Rioplatense dialect).

CONTEXT: You are translating science fiction and classic literature books.
Preserve literary style, proper nouns, and sci-fi terminology accurately.

CRITICAL RULES - FOLLOW EXACTLY:

1. VOSEO - Always use "vos" instead of "tú":
   - vos tenés (NOT tú tienes)
   - vos querés (NOT tú quieres)
   - vos podés (NOT tú puedes)
   - vos sabés (NOT tú sabes)
   - vos sos (NOT tú eres)

2. PLURAL YOU - Use "ustedes" (NOT "vosotros"):
   - ustedes tienen (NOT vosotros tenéis)

3. ARGENTINE VOCABULARY:
   - auto (NOT carro, coche)
   - celular (NOT móvil)
   - colectivo (NOT autobús)
   - computadora (NOT ordenador)
   - departamento (NOT piso)
   - manejar (NOT conducir)

4. PAST TENSE - Prefer simple past:
   - "Ayer comí" (NOT "Ayer he comido")

5. Use "acá" instead of "aquí", "allá" instead of "allí"

OUTPUT FORMAT:
Return ONLY a JSON object. No explanations, no comments, no markdown.
For single translation: {"text": "translated text here"}
For batch translation: {"translations": ["text1", "text2", ...]}

IMPORTANT: Never add any text outside the JSON. No "Here's the translation", no explanations.
"""

# European Spanish prompt
SYSTEM_PROMPT_ES = """You are an expert translator specializing in Russian to European Spanish (Castilian).

CONTEXT: You are translating science fiction and classic literature books.

CRITICAL RULES:
1. TUTEO - Use "tú" (NOT "vos")
2. PLURAL YOU - Use "vosotros" (NOT "ustedes")
3. EUROPEAN VOCABULARY: coche, móvil, autobús, ordenador, piso, conducir
4. PAST TENSE - Use compound past for recent: "Esta mañana he llegado"
5. Use "aquí" (NOT "acá"), "allí" (NOT "allá")

OUTPUT FORMAT:
Return ONLY a JSON object. No explanations, no comments, no markdown.
For single translation: {"text": "translated text here"}
For batch translation: {"translations": ["text1", "text2", ...]}
"""

# Map target language codes to prompts
LANGUAGE_PROMPTS = {
    "es-latam": SYSTEM_PROMPT_LATAM,
    "es-ar": SYSTEM_PROMPT_LATAM,
    "es-US": SYSTEM_PROMPT_LATAM,
    "es": SYSTEM_PROMPT_ES,
    "es-ES": SYSTEM_PROMPT_ES,
}


class GeminiTranslator(BaseTranslator):
    """
    Google Gemini translator with optimizations for free tier.

    Features:
    - Large batches (15 sentences per request) to minimize API calls
    - Rate limiting for free tier (15 RPM)
    - Parallel processing (conservative)

    Free tier (Gemini 1.5 Flash):
    - 15 RPM, 1M TPM, 1500 req/day
    - For 1500 sentences with batch_size=15: ~100 requests = 1 day's quota
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        batch_size: int = 15,
        max_workers: int = 2,
        target_dialect: str = "es-latam",
    ):
        """
        Initialize Gemini translator.

        Args:
            api_key: Gemini API key (or GEMINI_API_KEY env var)
            model: Model to use (gemini-1.5-flash for free tier)
            batch_size: Number of sentences per request (15 = good for free tier)
            max_workers: Parallel request threads (2 for free tier)
            target_dialect: Target Spanish dialect (es-latam, es)
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. "
                "Set GEMINI_API_KEY environment variable or pass api_key parameter."
            )

        genai.configure(api_key=self.api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.target_dialect = target_dialect
        self._last_request_time = 0.0

        # Choose prompt based on target dialect
        self.system_prompt = LANGUAGE_PROMPTS.get(target_dialect, SYSTEM_PROMPT_LATAM)

    def name(self) -> str:
        return f"Gemini {self.model_name} ({self.target_dialect})"

    def _rate_limit(self) -> None:
        """Apply rate limiting for free tier."""
        elapsed = time.time() - self._last_request_time
        if elapsed < THROTTLE_DELAY:
            time.sleep(THROTTLE_DELAY - elapsed)
        self._last_request_time = time.time()

    def _has_cyrillic(self, text: str) -> bool:
        """Check if text contains Cyrillic characters."""
        return bool(re.search('[а-яА-ЯёЁ]', text))

    def _has_latin(self, text: str) -> bool:
        """Check if text contains Latin characters."""
        return bool(re.search('[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]', text))

    def _validate_translation(self, original: str, translation: str, source_lang: str, target_lang: str) -> str:
        """
        Validate that translation is actually translated.
        Returns error message if invalid, empty string if valid.
        """
        # Check empty
        if not translation or not translation.strip():
            return "Empty translation"

        # Check same as original
        if translation.strip() == original.strip():
            return "Translation same as original"

        # Check target language has correct alphabet
        if target_lang in ("es", "es-latam", "es-ar", "es-ES", "en", "en-US", "en-GB"):
            # Target is Latin-based - must have Latin chars, must NOT have Cyrillic
            if not self._has_latin(translation):
                return f"No Latin characters in translation for {target_lang}"
            if self._has_cyrillic(translation):
                return f"Cyrillic found in {target_lang} translation"

        # Check source language chars NOT in translation (for ru->es/en)
        if source_lang == "ru" and target_lang not in ("ru", "uk", "be", "bg", "sr", "mk"):
            if self._has_cyrillic(translation):
                return "Cyrillic characters in non-Cyrillic target"

        return ""  # Valid

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from Gemini response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)

    def _translate_single(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single text with retry logic. Raises on invalid translation."""
        if not text.strip():
            return text

        prompt = f"{self.system_prompt}\n\nTranslate this text:\n{text}"

        last_error = None
        last_validation_error = None
        for attempt in range(MAX_RETRIES):
            try:
                self._rate_limit()

                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,
                    ),
                )

                result = self._parse_json_response(response.text)
                translation = result.get("text", "")

                validation_error = self._validate_translation(text, translation, source_lang, target_lang)
                if not validation_error:
                    return translation

                # Invalid translation - retry
                last_validation_error = validation_error
                print(f"    [Gemini] Invalid: {validation_error}, retrying ({attempt + 1}/{MAX_RETRIES})...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_DELAY)
                continue

            except google_exceptions.ResourceExhausted as e:
                last_error = e
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                print(f"    [Gemini] Rate limited, waiting {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                continue

            except json.JSONDecodeError as e:
                last_error = e
                print(f"    [Gemini] JSON parse error: {e}, retrying ({attempt + 1}/{MAX_RETRIES})...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_DELAY)
                continue

            except Exception as e:
                last_error = e
                print(f"    [Gemini] Error: {e}, retrying ({attempt + 1}/{MAX_RETRIES})...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_DELAY)
                continue

        # All retries exhausted - FAIL HARD
        error_msg = last_validation_error or str(last_error) or "Unknown error"
        raise RuntimeError(f"Translation FAILED after {MAX_RETRIES} retries: {error_msg}. Text: {text[:80]}...")

    def _translate_batch_internal(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a batch of texts in one API call."""
        if not texts:
            return []

        # Filter empty texts, keep track of positions
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            return texts

        # Create numbered input
        numbered_input = "\n".join(f"{i+1}. {t}" for i, (_, t) in enumerate(non_empty))
        prompt = f"{self.system_prompt}\n\nTranslate each line:\n{numbered_input}"

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                self._rate_limit()

                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,
                    ),
                )

                result = self._parse_json_response(response.text)
                translations = result.get("translations", [])

                # Reconstruct full list
                output = list(texts)
                invalid_indices = []
                for idx, (orig_pos, orig_text) in enumerate(non_empty):
                    if idx < len(translations):
                        translation = translations[idx]
                        validation_error = self._validate_translation(orig_text, translation, source_lang, target_lang)
                        if not validation_error:  # Empty string = valid
                            output[orig_pos] = translation
                        else:
                            invalid_indices.append((orig_pos, orig_text, validation_error))

                # Retry invalid translations individually
                if invalid_indices:
                    print(f"    [Gemini] {len(invalid_indices)} invalid translations in batch, retrying individually...")
                    for orig_pos, orig_text, val_error in invalid_indices:
                        print(f"      Invalid [{orig_pos}]: {val_error}")
                        try:
                            output[orig_pos] = self._translate_single(orig_text, source_lang, target_lang)
                        except RuntimeError:
                            raise RuntimeError(f"Batch translation failed for: {orig_text[:50]}...")

                return output

            except google_exceptions.ResourceExhausted as e:
                last_error = e
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                print(f"    [Gemini] Rate limited, waiting {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                continue

            except json.JSONDecodeError as e:
                print(f"    [Gemini] JSON parse error in batch: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_DELAY)
                continue

            except Exception as e:
                print(f"    [Gemini] Batch error: {e}")
                return texts

        print(f"    [Gemini] Batch max retries exceeded: {last_error}")
        raise RuntimeError(f"Batch translation failed after {MAX_RETRIES} retries")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate single text."""
        if source_lang == target_lang:
            return text
        # Update prompt if target language changed
        if target_lang != self.target_dialect and target_lang in LANGUAGE_PROMPTS:
            self.system_prompt = LANGUAGE_PROMPTS[target_lang]
            self.target_dialect = target_lang
        return self._translate_single(text, source_lang, target_lang)

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        show_progress: bool = True
    ) -> list[str]:
        """
        Translate multiple texts with batching and parallelization.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code
            show_progress: Show progress indicator

        Returns:
            List of translated texts
        """
        if source_lang == target_lang:
            return texts

        if not texts:
            return []

        # Update prompt if target language changed
        if target_lang != self.target_dialect and target_lang in LANGUAGE_PROMPTS:
            self.system_prompt = LANGUAGE_PROMPTS[target_lang]
            self.target_dialect = target_lang

        # Split into batches
        batches = []
        for i in range(0, len(texts), self.batch_size):
            batches.append((i, texts[i:i + self.batch_size]))

        results = [None] * len(texts)
        completed = 0
        total = len(batches)

        # Process batches in parallel (limited workers for free tier)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._translate_batch_internal,
                    batch,
                    source_lang,
                    target_lang
                ): start_idx
                for start_idx, batch in batches
            }

            for future in as_completed(futures):
                start_idx = futures[future]
                try:
                    batch_results = future.result()
                    for j, translation in enumerate(batch_results):
                        results[start_idx + j] = translation
                except Exception as e:
                    print(f"    [Gemini] Batch failed: {e}")
                    batch_size = min(self.batch_size, len(texts) - start_idx)
                    for j in range(batch_size):
                        if results[start_idx + j] is None:
                            results[start_idx + j] = texts[start_idx + j]

                completed += 1
                if show_progress:
                    print(f"    [Gemini] Progress: {completed}/{total} batches", end="\r")

        if show_progress:
            print()

        return [r if r is not None else texts[i] for i, r in enumerate(results)]
