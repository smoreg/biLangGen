"""OpenAI GPT translation provider with batching and parallelization.

Features:
- Structured Output: Guarantees clean JSON response, no "Here's your translation..."
- Batching: Multiple sentences per request to reduce overhead
- Parallelization: Concurrent requests for speed
- Prompt Caching: Long system prompt (>1024 tokens) for 50% discount on cached requests
- Argentine Spanish (Rioplatense): voseo, local vocabulary
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from openai import OpenAI, RateLimitError, APIError

from core.translator import BaseTranslator


# Rate limit handling constants
MAX_RETRIES = 5
BASE_DELAY = 0.5  # Base delay in seconds
MAX_DELAY = 30.0  # Maximum delay between retries

# OpenAI GPT-4o-mini rate limits (Tier 1):
# - 200,000 TPM (tokens per minute)
# - 500 RPM (requests per minute)
# - 10,000 RPD (requests per day)
# For safety, we throttle to ~150k TPM (~2500 tokens/sec)
# Average request: ~1200 tokens (system prompt) + ~200 tokens (batch) = ~1400 tokens
# Safe parallel workers: min(500 RPM / 60, 150k TPM / 1400) = ~8 workers
MAX_SAFE_WORKERS = 8
THROTTLE_DELAY = 0.1  # Delay between batch submissions (seconds)


# Long system prompt for prompt caching (>1024 tokens = automatic 50% discount)
# This prompt is designed to be comprehensive AND trigger OpenAI's prompt caching
SYSTEM_PROMPT_LATAM = """RU→ES-AR translator. Sci-fi/literature. JSON only.

CRITICAL: ZERO CYRILLIC in output! Latin alphabet ONLY.
- Transliterate ALL names: Влэй→Vley, Иван→Iván, СССР→URSS
- Single Cyrillic char = ERROR

VOSEO (NOT tú): vos tenés/querés/podés/sabés/sos
PLURAL: ustedes (NOT vosotros)
VOCAB: auto, celular, colectivo, computadora, acá/allá
PAST: pretérito simple (comí, NOT he comido)

Output: {"text":"..."} or {"translations":[...]}
No markdown, no explanations."""

# Shorter prompt for minimal overhead
SYSTEM_PROMPT_SHORT = """RU→ES-AR, voseo. ZERO CYRILLIC—Latin only! Names: Влэй→Vley.
JSON: {"text":"..."} or {"translations":[...]}"""


# European Spanish (Spain) system prompt
SYSTEM_PROMPT_ES = """You are an expert translator specializing in Russian to European Spanish (Castilian).

CONTEXT: You are translating science fiction and classic literature books.
Preserve literary style, proper nouns, and sci-fi terminology accurately.

IMPORTANT TERMS:
- "машина времени" = "máquina del tiempo" (NOT "carro del tiempo")
- "путешественник во времени" = "viajero del tiempo" / "viajero temporal"
- "космический корабль" = "nave espacial"
- "инопланетянин" = "extraterrestre" / "alienígena"
- "робот" = "robot"
- "андроид" = "androide"
- "искусственный интеллект" = "inteligencia artificial"
- "телепортация" = "teletransportación"
- "гиперпространство" = "hiperespacio"
- "параллельная вселенная" = "universo paralelo"
- "чёрная дыра" = "agujero negro"
- "галактика" = "galaxia"
- "звездолёт" = "nave estelar"

CRITICAL RULES - FOLLOW EXACTLY:

1. TUTEO - Use "tú" (NOT "vos"):
   - tú tienes (NOT vos tenés)
   - tú quieres (NOT vos querés)
   - tú puedes (NOT vos podés)
   - tú sabes (NOT vos sabés)
   - tú vienes (NOT vos venís)
   - tú dices (NOT vos decís)
   - tú haces (NOT vos hacés)
   - tú eres (NOT vos sos)
   - tú estás (NOT vos estás)

2. PLURAL YOU - Use "vosotros" (NOT "ustedes"):
   - vosotros tenéis (NOT ustedes tienen)
   - vosotros queréis (NOT ustedes quieren)
   - vosotros podéis (NOT ustedes pueden)

3. EUROPEAN SPANISH VOCABULARY:
   - coche (NOT auto, carro)
   - móvil / teléfono móvil (NOT celular)
   - autobús (NOT colectivo, bus)
   - piso / apartamento (NOT departamento)
   - ordenador (NOT computadora)
   - frigorífico / nevera (NOT heladera)
   - piscina (NOT pileta)
   - dinero (NOT plata) - formal
   - trabajo (NOT laburo) - formal
   - chico/chica (NOT pibe/piba) - standard
   - conducir (NOT manejar)
   - vale - OK, sure
   - tío/tía - buddy, mate (informal address)
   - guay - cool, great
   - molar - to be cool
   - currar - to work (informal)
   - pasta - money (informal)

4. GRAMMAR NOTES:
   - Use "aquí" (NOT "acá")
   - Use "allí" (NOT "allá")
   - Diminutives: -ito/-ita are common (cafecito, ratito)
   - Leísmo is acceptable: "le vi" instead of "lo vi"

5. PAST TENSE:
   - Use compound past (pretérito perfecto) for recent actions:
   - "Esta mañana he llegado" (NOT "Esta mañana llegué")
   - "Hoy he comido" (NOT "Hoy comí")

6. REGISTER:
   - For literary/narrative text: Use moderately formal register with tuteo
   - For dialogue: Use natural spoken European Spanish
   - Preserve the tone and style of the original

TRANSLATION EXAMPLES:
- "Привет, как дела?" → "Hola, ¿qué tal?"
- "У тебя есть машина?" → "¿Tienes coche?"
- "Мне нужно позвонить" → "Necesito llamar por el móvil"
- "Ты знаешь где автобусная остановка?" → "¿Sabes dónde está la parada del autobús?"
- "Он работает программистом" → "Trabaja de programador"
- "Это очень дорого" → "Es muy caro"
- "Пойдём в бассейн" → "Vamos a la piscina"
- "Подожди минутку" → "Espera un momento"

OUTPUT FORMAT:
Return ONLY a JSON object. No explanations, no comments, no markdown.
For single translation: {"text": "translated text here"}
For batch translation: {"translations": ["text1", "text2", ...]}

IMPORTANT: Never add any text outside the JSON. No "Here's the translation", no explanations.
"""

# Short prompt for European Spanish
SYSTEM_PROMPT_ES_SHORT = """Translate RU→ES (European Spanish, tuteo: tú tienes/quieres/puedes, vosotros).
Output JSON only: {"text": "..."} or {"translations": [...]}"""


# English system prompt
SYSTEM_PROMPT_EN = """You are an expert translator specializing in Russian to English.

CONTEXT: You are translating science fiction and classic literature books.
Preserve literary style, proper nouns, and sci-fi terminology accurately.

CRITICAL RULES:
1. Translate Russian text to natural, fluent English
2. Preserve the tone and style of the original
3. For literary/narrative text: Use moderately formal register
4. For dialogue: Use natural spoken English
5. Transliterate Russian names appropriately (Иван→Ivan, Владимир→Vladimir)
6. NO Cyrillic characters in output - English alphabet only

IMPORTANT TERMS:
- "машина времени" = "time machine"
- "путешественник во времени" = "time traveler"
- "космический корабль" = "spaceship"
- "инопланетянин" = "alien" / "extraterrestrial"
- "робот" = "robot"
- "андроид" = "android"
- "искусственный интеллект" = "artificial intelligence"
- "телепортация" = "teleportation"
- "гиперпространство" = "hyperspace"
- "параллельная вселенная" = "parallel universe"
- "чёрная дыра" = "black hole"

OUTPUT FORMAT:
Return ONLY a JSON object. No explanations, no comments, no markdown.
For single translation: {"text": "translated text here"}
For batch translation: {"translations": ["text1", "text2", ...]}

IMPORTANT: Never add any text outside the JSON. No "Here's the translation", no explanations.
"""

SYSTEM_PROMPT_EN_SHORT = """Translate RU→EN (natural fluent English). NO Cyrillic in output.
Output JSON only: {"text": "..."} or {"translations": [...]}"""


# Map target language codes to prompts
LANGUAGE_PROMPTS = {
    "es-latam": (SYSTEM_PROMPT_LATAM, SYSTEM_PROMPT_SHORT),
    "es-ar": (SYSTEM_PROMPT_LATAM, SYSTEM_PROMPT_SHORT),
    "es-US": (SYSTEM_PROMPT_LATAM, SYSTEM_PROMPT_SHORT),
    "es": (SYSTEM_PROMPT_ES, SYSTEM_PROMPT_ES_SHORT),
    "es-ES": (SYSTEM_PROMPT_ES, SYSTEM_PROMPT_ES_SHORT),
    "en": (SYSTEM_PROMPT_EN, SYSTEM_PROMPT_EN_SHORT),
    "en-US": (SYSTEM_PROMPT_EN, SYSTEM_PROMPT_EN_SHORT),
    "en-GB": (SYSTEM_PROMPT_EN, SYSTEM_PROMPT_EN_SHORT),
}


class OpenAIGPTTranslator(BaseTranslator):
    """
    OpenAI GPT-4o-mini translator with optimizations.

    Features:
    - Structured output (JSON schema) - no extra text in response
    - Batching - multiple sentences per request
    - Parallel processing - concurrent API calls
    - Prompt caching - 50% discount on repeated prompts

    Pricing (GPT-4o-mini):
    - Input: $0.15/1M tokens (cached: $0.075/1M)
    - Output: $0.60/1M tokens

    For 6.7M chars (~1.7M tokens) ≈ $1-2 total
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        batch_size: int = 10,
        max_workers: int = 4,
        use_long_prompt: bool = True,
        target_dialect: str = "es-latam",
        translate_context: Optional[str] = None,
    ):
        """
        Initialize OpenAI GPT translator.

        Args:
            api_key: OpenAI API key (or OPENAI_API_KEY env var)
            model: Model to use (gpt-4o-mini recommended for cost)
            batch_size: Number of sentences per request (10 = good balance)
            max_workers: Parallel request threads
            use_long_prompt: Use long prompt for caching (recommended)
            target_dialect: Target Spanish dialect (es-latam, es-ar, es-mx, es)
            translate_context: Context about the text being translated (book name, genre, etc.)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.target_dialect = target_dialect
        self.use_long_prompt = use_long_prompt
        self.translate_context = translate_context

        # Choose prompt based on target dialect and caching preference
        self._update_prompt_for_dialect(target_dialect)

    def _update_prompt_for_dialect(self, dialect: str):
        """Update system prompt based on target dialect."""
        if dialect not in LANGUAGE_PROMPTS:
            available = ", ".join(sorted(LANGUAGE_PROMPTS.keys()))
            raise ValueError(
                f"Unsupported target language: '{dialect}'. "
                f"Available: {available}"
            )
        long_prompt, short_prompt = LANGUAGE_PROMPTS[dialect]
        base_prompt = long_prompt if self.use_long_prompt else short_prompt

        # Add user-provided context to the prompt
        if self.translate_context:
            context_addition = f"\n\nCONTEXT: {self.translate_context}\nUse this context for proper nouns, terminology, and style."
            self.system_prompt = base_prompt + context_addition
        else:
            self.system_prompt = base_prompt

        # Response format for structured output
        self.response_format_single = {
            "type": "json_schema",
            "json_schema": {
                "name": "translation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"}
                    },
                    "required": ["text"],
                    "additionalProperties": False
                }
            }
        }

        self.response_format_batch = {
            "type": "json_schema",
            "json_schema": {
                "name": "translations",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "translations": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["translations"],
                    "additionalProperties": False
                }
            }
        }

    def name(self) -> str:
        return f"OpenAI {self.model} ({self.target_dialect})"

    def _count_cyrillic(self, text: str) -> int:
        """Count Cyrillic characters in text."""
        return len(re.findall('[а-яА-ЯёЁ]', text))

    def _has_cyrillic(self, text: str) -> bool:
        """Check if text contains Cyrillic characters."""
        return self._count_cyrillic(text) > 0

    def _validate_translation(self, original: str, translation: str, source_lang: str, target_lang: str) -> bool:
        """Validate that translation is actually translated.

        Returns True if translation is valid, False if it needs retry.
        """
        # If same as original, it's not translated
        if translation.strip() == original.strip():
            return False

        # If translating FROM Russian to non-Russian, NO Cyrillic allowed
        # Names must be transliterated (Влэй → Vley)
        if source_lang == "ru" and target_lang not in ("ru", "uk", "be", "bg", "sr", "mk"):
            if self._has_cyrillic(translation):
                return False

        return True

    def _parse_retry_delay(self, error_message: str) -> float:
        """Extract retry delay from rate limit error message."""
        # Try to find "Please try again in Xms" or "Please try again in X.Xs"
        match = re.search(r'try again in (\d+(?:\.\d+)?)(ms|s)', str(error_message))
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit == 'ms':
                return value / 1000.0
            return value
        return BASE_DELAY

    def _translate_single(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single text with retry logic for rate limits and validation."""
        if not text.strip():
            return text

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": text}
                    ],
                    response_format=self.response_format_single,
                    temperature=0.3,
                )

                result = json.loads(response.choices[0].message.content)
                translation = result.get("text", text)

                # Validate translation
                if self._validate_translation(text, translation, source_lang, target_lang):
                    return translation

                # Invalid translation - log details and retry
                is_same = translation.strip() == text.strip()
                has_cyr = self._has_cyrillic(translation)
                print(f"    [OpenAI] Invalid: same={is_same}, cyrillic={has_cyr}")
                print(f"      IN:  {text[:60]}{'...' if len(text) > 60 else ''}")
                print(f"      OUT: {translation[:60]}{'...' if len(translation) > 60 else ''}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(0.5)
                    # Try with slightly higher temperature
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": f"TRANSLATE TO SPANISH (not Russian): {text}"}
                        ],
                        response_format=self.response_format_single,
                        temperature=0.5,
                    )
                    result = json.loads(response.choices[0].message.content)
                    translation = result.get("text", text)
                    if self._validate_translation(text, translation, source_lang, target_lang):
                        return translation
                continue

            except RateLimitError as e:
                last_error = e
                delay = self._parse_retry_delay(str(e))
                # Exponential backoff with jitter
                delay = min(delay * (2 ** attempt), MAX_DELAY)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                continue

            except APIError as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    last_error = e
                    delay = self._parse_retry_delay(str(e))
                    delay = min(delay * (2 ** attempt), MAX_DELAY)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(delay)
                    continue
                print(f"    [OpenAI] API error: {e}")
                return text

            except Exception as e:
                print(f"    [OpenAI] Error translating: {e}")
                return text

        print(f"    [OpenAI] Max retries exceeded: {last_error}")
        raise RuntimeError(f"Translation failed after {MAX_RETRIES} retries: {text[:50]}...")

    def _translate_batch_internal(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a batch of texts in one API call with retry logic."""
        if not texts:
            return []

        # Filter empty texts, keep track of positions
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            return texts

        # Create numbered input for clarity
        numbered_input = "\n".join(f"{i+1}. {t}" for i, (_, t) in enumerate(non_empty))

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Translate each line:\n{numbered_input}"}
                    ],
                    response_format=self.response_format_batch,
                    temperature=0.3,
                )

                result = json.loads(response.choices[0].message.content)
                translations = result.get("translations", [])

                # Reconstruct full list with empty texts preserved
                output = list(texts)  # Copy original
                invalid_indices = []
                for idx, (orig_pos, orig_text) in enumerate(non_empty):
                    if idx < len(translations):
                        translation = translations[idx]
                        # Validate each translation
                        if self._validate_translation(orig_text, translation, source_lang, target_lang):
                            output[orig_pos] = translation
                        else:
                            invalid_indices.append((orig_pos, orig_text))

                # Retry invalid translations individually
                if invalid_indices:
                    print(f"    [OpenAI] {len(invalid_indices)} invalid translations in batch, retrying individually...")
                    for orig_pos, orig_text in invalid_indices:
                        try:
                            output[orig_pos] = self._translate_single(orig_text, source_lang, target_lang)
                        except RuntimeError:
                            raise RuntimeError(f"Batch translation validation failed for: {orig_text[:50]}...")

                return output

            except RateLimitError as e:
                last_error = e
                delay = self._parse_retry_delay(str(e))
                delay = min(delay * (2 ** attempt), MAX_DELAY)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                continue

            except APIError as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    last_error = e
                    delay = self._parse_retry_delay(str(e))
                    delay = min(delay * (2 ** attempt), MAX_DELAY)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(delay)
                    continue
                print(f"    [OpenAI] API batch error: {e}")
                return texts

            except Exception as e:
                print(f"    [OpenAI] Batch error: {e}")
                return texts

        print(f"    [OpenAI] Batch max retries exceeded: {last_error}")
        raise RuntimeError(f"Batch translation failed after {MAX_RETRIES} retries")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate single text."""
        if source_lang == target_lang:
            return text
        # Update prompt if target language changed
        if target_lang != self.target_dialect and target_lang in LANGUAGE_PROMPTS:
            self._update_prompt_for_dialect(target_lang)
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
            self._update_prompt_for_dialect(target_lang)
            self.target_dialect = target_lang

        # Split into batches
        batches = []
        for i in range(0, len(texts), self.batch_size):
            batches.append((i, texts[i:i + self.batch_size]))

        results = [None] * len(texts)
        completed = 0
        total = len(batches)

        # Process batches in parallel
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
                    print(f"    [OpenAI] Batch failed: {e}")
                    # Keep original texts for failed batch
                    batch_size = min(self.batch_size, len(texts) - start_idx)
                    for j in range(batch_size):
                        if results[start_idx + j] is None:
                            results[start_idx + j] = texts[start_idx + j]

                completed += 1
                if show_progress:
                    print(f"    [OpenAI] Progress: {completed}/{total} batches", end="\r")

        if show_progress:
            print()  # New line after progress

        # Fill any None values with original
        return [r if r is not None else texts[i] for i, r in enumerate(results)]

    def translate_batch_async(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        output_file: str = "batch_translations.jsonl"
    ) -> str:
        """
        Create OpenAI Batch API request for 50% discount.

        Returns path to JSONL file ready for upload.
        Processing takes up to 24h but costs 50% less.

        Args:
            texts: Texts to translate
            source_lang: Source language
            target_lang: Target language
            output_file: Output JSONL file path

        Returns:
            Path to created JSONL file
        """
        tasks = []

        # Split into batches
        for batch_idx, i in enumerate(range(0, len(texts), self.batch_size)):
            batch = texts[i:i + self.batch_size]
            numbered_input = "\n".join(f"{j+1}. {t}" for j, t in enumerate(batch) if t.strip())

            task = {
                "custom_id": f"batch-{batch_idx}-start-{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.model,
                    "temperature": 0.3,
                    "response_format": self.response_format_batch,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Translate each line:\n{numbered_input}"}
                    ]
                }
            }
            tasks.append(task)

        # Write JSONL file
        with open(output_file, 'w', encoding='utf-8') as f:
            for task in tasks:
                f.write(json.dumps(task, ensure_ascii=False) + '\n')

        print(f"    [OpenAI] Created batch file: {output_file}")
        print(f"    [OpenAI] Total batches: {len(tasks)}")
        print(f"    [OpenAI] To submit:")
        print(f"             openai api batches create -i {output_file} -e /v1/chat/completions -c 24h")

        return output_file

    def submit_batch(self, jsonl_file: str) -> str:
        """
        Submit batch file to OpenAI Batch API.

        Args:
            jsonl_file: Path to JSONL file

        Returns:
            Batch job ID
        """
        # Upload file
        with open(jsonl_file, "rb") as f:
            batch_file = self.client.files.create(file=f, purpose="batch")

        # Create batch job
        batch_job = self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )

        print(f"    [OpenAI] Batch submitted: {batch_job.id}")
        print(f"    [OpenAI] Status: {batch_job.status}")
        print(f"    [OpenAI] Check with: openai api batches retrieve {batch_job.id}")

        return batch_job.id

    def check_batch_status(self, batch_id: str) -> dict:
        """Check status of a batch job."""
        batch = self.client.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.status,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "request_counts": batch.request_counts,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
        }

    def download_batch_results(self, batch_id: str, output_file: str = "batch_results.jsonl") -> list[str]:
        """
        Download and parse batch results.

        Args:
            batch_id: Batch job ID
            output_file: Where to save results

        Returns:
            List of translated texts in order
        """
        batch = self.client.batches.retrieve(batch_id)

        if batch.status != "completed":
            raise ValueError(f"Batch not completed. Status: {batch.status}")

        if not batch.output_file_id:
            raise ValueError("No output file available")

        # Download results
        content = self.client.files.content(batch.output_file_id).content
        with open(output_file, 'wb') as f:
            f.write(content)

        # Parse results
        results = {}
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                result = json.loads(line.strip())
                custom_id = result['custom_id']
                # Parse "batch-{idx}-start-{start_idx}"
                parts = custom_id.split('-')
                start_idx = int(parts[-1])

                response_body = result['response']['body']
                translations = json.loads(
                    response_body['choices'][0]['message']['content']
                ).get('translations', [])

                for j, trans in enumerate(translations):
                    results[start_idx + j] = trans

        # Convert to ordered list
        max_idx = max(results.keys()) if results else -1
        return [results.get(i, "") for i in range(max_idx + 1)]

    # ============================================================
    # WORD TRANSLATION (reverse direction: ES→RU for rare words)
    # ============================================================

    def translate_words_batch(
        self,
        words: list[str],
        source_lang: str,
        target_lang: str,
        batch_size: int = 50,
        show_progress: bool = True
    ) -> dict[str, str]:
        """
        Translate a list of words (for rare words ES→RU).

        Unlike sentence translation, this:
        - Translates in reverse direction (target→source)
        - Returns dict mapping word→translation
        - No validation (words can stay the same if untranslatable)

        Args:
            words: List of words to translate
            source_lang: Source language (e.g., 'es-latam')
            target_lang: Target language (e.g., 'ru')
            batch_size: Words per API call
            show_progress: Print progress

        Returns:
            Dict mapping each word to its translation
        """
        if not words:
            return {}

        # Deduplicate
        unique_words = list(dict.fromkeys(words))

        # Split into batches
        batches = [unique_words[i:i + batch_size] for i in range(0, len(unique_words), batch_size)]

        all_translations = {}

        for i, batch in enumerate(batches):
            if show_progress:
                print(f"    [OpenAI] Words batch {i+1}/{len(batches)} ({len(batch)} words)...")

            translations = self._translate_words_internal(batch, source_lang, target_lang)
            all_translations.update(translations)

            # Small delay between batches
            if i < len(batches) - 1:
                time.sleep(0.1)

        if show_progress:
            print(f"    [OpenAI] Translated {len(all_translations)}/{len(unique_words)} words")

        return all_translations

    def _translate_words_internal(
        self,
        words: list[str],
        source_lang: str,
        target_lang: str
    ) -> dict[str, str]:
        """Translate a batch of words, returns dict."""
        if not words:
            return {}

        # Normalize source lang for prompt
        src_display = source_lang.upper().replace("-", " ")
        tgt_display = target_lang.upper()

        word_list = json.dumps(words, ensure_ascii=False)

        prompt = f"Translate these {src_display} words to {tgt_display}. Return JSON dict mapping each word to translation.\nWords: {word_list}"

        system = f"""Word translator {src_display}→{tgt_display}. Dictionary style.
Rules:
- Translate each word to {tgt_display}
- Short translations (1-2 words max)
- Nouns→nouns, verbs→infinitives
- ZERO {src_display} characters in output - use {tgt_display} alphabet only
Output: {{"word1": "перевод1", "word2": "перевод2"}}"""

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )

                result = json.loads(response.choices[0].message.content)

                # Handle both dict and list responses
                if isinstance(result, dict):
                    # Filter out empty translations
                    return {k: v for k, v in result.items() if v}
                elif isinstance(result, list):
                    # If GPT returns list, map to original words
                    return {words[i]: result[i] for i in range(min(len(words), len(result))) if result[i]}

                return {}

            except RateLimitError as e:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                if attempt < MAX_RETRIES - 1:
                    print(f"    [OpenAI] Words rate limited, waiting {delay:.1f}s...")
                    time.sleep(delay)
                continue

            except APIError as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(delay)
                    continue
                print(f"    [OpenAI] Words API error: {e}")
                return {}

            except Exception as e:
                print(f"    [OpenAI] Words error: {e}")
                return {}

        print(f"    [OpenAI] Words max retries exceeded")
        return {}
