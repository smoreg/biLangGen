"""OpenAI GPT translator for rare words (single words with context).

Unlike sentences, single words need special handling:
- Words without context are often mistranslated
- Batch processing reduces API calls
- Dictionary-style output format

Example:
  Input: ["armadillos", "guaridas", "escondites"]
  Output: {"armadillos": "броненосцы", "guaridas": "норы", "escondites": "укрытия"}
"""

import json
import os
import time
from typing import Dict, List, Optional

from openai import OpenAI, RateLimitError, APIError


MAX_RETRIES = 5
BASE_DELAY = 0.5
MAX_DELAY = 30.0
BATCH_SIZE = 50  # Words per request (can handle more since words are short)


# System prompt for word translation (dictionary-style)
SYSTEM_PROMPT_WORDS = """You are a bilingual dictionary translating individual words.

TASK: Translate each Spanish word to Russian.

RULES:
1. Translate the WORD ITSELF, not a random phrase
2. Use the most common translation for each word
3. Keep it SHORT - one word or short phrase
4. For nouns, give the noun translation (not verb or adjective)
5. For verbs, give the infinitive form in Russian

EXAMPLES:
- armadillos → броненосцы (the animals!)
- guaridas → норы / логова / берлоги
- escondites → укрытия / тайники
- crías → детёныши
- moretones → синяки
- párpados → веки
- depredadores → хищники
- sobrevivir → выживать
- aterrizaje → посадка / приземление
- tripulación → экипаж

OUTPUT FORMAT:
Return ONLY a JSON object mapping each word to its translation.
{"word1": "перевод1", "word2": "перевод2", ...}

IMPORTANT: Never return empty translations. Every word must have a translation.
"""


class OpenAIWordsTranslator:
    """
    OpenAI GPT translator optimized for single words.

    Features:
    - Batch processing (50 words per request)
    - Dictionary-style output
    - Context-aware prompting
    - Retry logic for rate limits
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        batch_size: int = BATCH_SIZE,
    ):
        """
        Initialize OpenAI words translator.

        Args:
            api_key: OpenAI API key (or OPENAI_API_KEY env var)
            model: Model to use (gpt-4o-mini recommended)
            batch_size: Words per API request
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.batch_size = batch_size

        # For word translations, we use json_object mode instead of strict schema
        # because we don't know the exact word keys in advance
        self.response_format = {"type": "json_object"}

    def _translate_batch(self, words: List[str], source_lang: str, target_lang: str) -> Dict[str, str]:
        """Translate a batch of words."""
        if not words:
            return {}

        # Build word list for prompt
        word_list = "\n".join(f"- {w}" for w in words)

        prompt = f"Translate these {source_lang.upper()} words to {target_lang.upper()}:\n{word_list}"

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_WORDS},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=self.response_format,
                    temperature=0.2,  # Low temperature for consistency
                )

                result = json.loads(response.choices[0].message.content)
                return result

            except RateLimitError as e:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                if attempt < MAX_RETRIES - 1:
                    print(f"    [OpenAI Words] Rate limited, waiting {delay:.1f}s...")
                    time.sleep(delay)
                continue

            except APIError as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(delay)
                    continue
                print(f"    [OpenAI Words] API error: {e}")
                return {}

            except Exception as e:
                print(f"    [OpenAI Words] Error: {e}")
                return {}

        print(f"    [OpenAI Words] Max retries exceeded")
        return {}

    def translate_words(
        self,
        words: List[str],
        source_lang: str,
        target_lang: str,
        show_progress: bool = True
    ) -> Dict[str, str]:
        """
        Translate list of words to target language.

        Args:
            words: List of words to translate
            source_lang: Source language code (es, en, etc.)
            target_lang: Target language code (ru, etc.)
            show_progress: Show progress indicator

        Returns:
            Dict mapping each word to its translation
        """
        if not words:
            return {}

        # Remove duplicates while preserving order
        unique_words = list(dict.fromkeys(words))

        # Split into batches
        batches = []
        for i in range(0, len(unique_words), self.batch_size):
            batches.append(unique_words[i:i + self.batch_size])

        all_translations = {}

        for i, batch in enumerate(batches):
            if show_progress:
                print(f"    [OpenAI Words] Translating batch {i+1}/{len(batches)} ({len(batch)} words)...")

            translations = self._translate_batch(batch, source_lang, target_lang)
            all_translations.update(translations)

            # Small delay between batches to avoid rate limits
            if i < len(batches) - 1:
                time.sleep(0.1)

        if show_progress:
            print(f"    [OpenAI Words] Translated {len(all_translations)} words")

        return all_translations

    def translate_word(self, word: str, source_lang: str, target_lang: str) -> str:
        """Translate a single word (uses batch internally)."""
        result = self.translate_words([word], source_lang, target_lang, show_progress=False)
        return result.get(word, word)
