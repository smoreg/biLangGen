"""Word frequency analysis for identifying rare words."""

import re
from typing import Optional

try:
    from wordfreq import zipf_frequency
    WORDFREQ_AVAILABLE = True
except ImportError:
    WORDFREQ_AVAILABLE = False

# Lazy-loaded spaCy models for lemmatization
_SPACY_MODELS = {}

def get_spacy_model(lang: str):
    """Get spaCy model for language (lazy-loaded, cached)."""
    global _SPACY_MODELS

    if lang in _SPACY_MODELS:
        return _SPACY_MODELS[lang]

    try:
        import spacy
        # Map language codes to spaCy models
        model_map = {
            "es": "es_core_news_sm",
            "es-latam": "es_core_news_sm",  # Same model for LatAm
            "en": "en_core_web_sm",
            "ru": "ru_core_news_sm",
        }
        model_name = model_map.get(lang)
        if model_name:
            nlp = spacy.load(model_name, disable=["ner", "parser"])  # Faster without NER/parser
            _SPACY_MODELS[lang] = nlp
            return nlp
    except (ImportError, OSError):
        pass

    _SPACY_MODELS[lang] = None
    return None

from core.languages import (
    RUSSIAN, ENGLISH, SPANISH, SPANISH_LATAM,
    get_language, get_wordfreq_code, UnsupportedLanguageError
)


# Common stopwords to skip (very basic list)
STOPWORDS = {
    RUSSIAN.code: {"и", "в", "на", "с", "по", "за", "к", "от", "из", "у", "о", "а", "но", "что", "как", "это", "он", "она", "они", "мы", "вы", "я", "ты", "не", "да", "же", "бы", "ли", "то", "так", "все", "для", "до", "при", "его", "её", "их", "мой", "твой", "наш", "ваш", "свой", "этот", "тот", "такой", "который", "когда", "где", "если", "чтобы", "потому", "только", "уже", "ещё", "очень", "можно", "нужно", "быть", "есть", "был", "была", "были", "будет"},
    ENGLISH.code: {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "and", "but", "if", "or", "because", "until", "while", "it", "its", "this", "that", "these", "those", "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "am"},
    SPANISH.code: {"el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "de", "del", "en", "con", "por", "para", "a", "al", "que", "es", "son", "está", "están", "fue", "fueron", "ser", "estar", "tener", "hacer", "como", "pero", "más", "ya", "muy", "también", "solo", "sin", "sobre", "entre", "hasta", "desde", "durante", "si", "no", "sí", "yo", "tú", "él", "ella", "nosotros", "vosotros", "ellos", "ellas", "mi", "tu", "su", "nuestro", "vuestro", "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas", "qué", "quién", "cuál", "cuándo", "dónde", "cómo", "cuánto", "hay", "había", "ha", "han", "he", "hemos", "me", "te", "se", "le", "les", "lo", "nos", "os"},
}
# es-latam uses same stopwords as es
STOPWORDS[SPANISH_LATAM.code] = STOPWORDS[SPANISH.code]


class WordFrequencyAnalyzer:
    """Analyzes word frequency to identify rare words."""

    def __init__(self, language: str = ENGLISH.code, zipf_threshold: float = 4.5):
        """
        Initialize analyzer.

        Args:
            language: Language code (ru, en, es, es-latam)
            zipf_threshold: Zipf score threshold (lower = rarer, 1-7 scale)
                           Words with score below this are considered rare

        Raises:
            UnsupportedLanguageError: If language is not supported
        """
        # Validate language
        lang = get_language(language)
        if lang is None:
            raise UnsupportedLanguageError(language, "WordFrequencyAnalyzer")

        self.language = lang.code
        self._wordfreq_code = get_wordfreq_code(lang.code)  # For wordfreq library
        self.zipf_threshold = zipf_threshold

        # Get stopwords - use base code for Spanish variants
        base_code = lang.code.split("-")[0]
        self.stopwords = STOPWORDS.get(lang.code, STOPWORDS.get(base_code, set()))

        # Lazy-load spaCy model for lemmatization
        self._nlp = None

    def _get_nlp(self):
        """Get spaCy model (lazy loaded)."""
        if self._nlp is None:
            self._nlp = get_spacy_model(self.language)
        return self._nlp

    def lemmatize(self, word: str) -> str:
        """Get lemma (base form) of a word. Falls back to lowercase if no spaCy."""
        nlp = self._get_nlp()
        if nlp:
            doc = nlp(word)
            if doc:
                return doc[0].lemma_.lower()
        return word.lower()

    def get_top_rare_per_sentence(
        self,
        sentences: list[str],
        max_per_sentence: int = 5,
        use_lemmas: bool = True,
    ) -> list[list[tuple[str, float, str]]]:
        """
        Get top-N rarest words from EACH sentence independently.

        This is the NEW logic: instead of global rarity threshold,
        we take the N words with lowest zipf score from each sentence.

        Args:
            sentences: List of sentences
            max_per_sentence: Maximum words per sentence (default 5)
            use_lemmas: Use lemmatization to deduplicate (default True)

        Returns:
            List of lists, each containing (original_word, zipf_score, lemma) tuples
            sorted by rarity (lowest zipf first)
        """
        result = []
        seen_lemmas = set()  # Track seen lemmas across all sentences

        for sentence in sentences:
            # Extract words with spaCy (if available) for lemmas
            nlp = self._get_nlp() if use_lemmas else None

            # Get all valid words with scores
            word_data = []  # [(original, zipf, lemma), ...]

            if nlp:
                doc = nlp(sentence)
                for token in doc:
                    # Skip punctuation, spaces, digits
                    if token.is_punct or token.is_space or token.is_digit:
                        continue
                    word = token.text
                    lemma = token.lemma_.lower()

                    # Skip stopwords (check both word and lemma)
                    if word.lower() in self.stopwords or lemma in self.stopwords:
                        continue
                    # Skip short words
                    if len(word) < 3:
                        continue

                    # Get zipf score for LEMMA (more accurate)
                    score = self.get_zipf_score(lemma)
                    if score > 0:  # Valid word
                        word_data.append((word, score, lemma))
            else:
                # Fallback: regex extraction
                words = self.extract_words(sentence)
                for word in words:
                    if len(word) < 3:
                        continue
                    if word.lower() in self.stopwords:
                        continue
                    if word.isdigit():
                        continue

                    lemma = word.lower()  # No lemmatization
                    score = self.get_zipf_score(word)
                    if score > 0:
                        word_data.append((word, score, lemma))

            # Sort by zipf score (lowest = rarest first)
            word_data.sort(key=lambda x: x[1])

            # Deduplicate by lemma within sentence
            sentence_result = []
            sentence_lemmas = set()
            for word, score, lemma in word_data:
                if lemma in sentence_lemmas:
                    continue
                # Skip if lemma already used in previous sentences
                if lemma in seen_lemmas:
                    continue

                sentence_lemmas.add(lemma)
                seen_lemmas.add(lemma)
                sentence_result.append((word, score, lemma))

                if len(sentence_result) >= max_per_sentence:
                    break

            result.append(sentence_result)

        return result

    def extract_global_rare_words(
        self,
        sentences: list[str],
        max_words: int = None,
        min_zipf: float = 0.5,
    ) -> dict[str, dict]:
        """
        Extract globally rare words from entire text.

        Creates a global TOP of rare words ranked by rarity (lowest zipf first).

        Args:
            sentences: List of sentences
            max_words: Max rare words to track. If None, uses sqrt(total_unique_words) * 2
            min_zipf: Minimum zipf score (filter out extremely rare/unknown words)

        Returns:
            Dict mapping word -> {zipf: float, rank: int, sentences: list[int]}
        """
        import math

        # Collect all words with sentences they appear in
        word_sentences = {}  # word -> list of sentence indices
        word_counts = {}  # word -> count in corpus

        for sent_idx, sentence in enumerate(sentences):
            words = self.extract_words(sentence)
            for word in words:
                word_lower = word.lower()
                if len(word_lower) < 3:
                    continue
                if word_lower in self.stopwords:
                    continue
                if word_lower.isdigit():
                    continue

                if word_lower not in word_sentences:
                    word_sentences[word_lower] = []
                if sent_idx not in word_sentences[word_lower]:
                    word_sentences[word_lower].append(sent_idx)
                word_counts[word_lower] = word_counts.get(word_lower, 0) + 1

        # Get zipf scores for all unique words
        word_scores = []
        for word in word_sentences:
            score = self.get_zipf_score(word)
            # Filter: must have valid score, be below threshold, above min_zipf
            if score >= min_zipf and score < self.zipf_threshold:
                word_scores.append((word, score))

        # Sort by rarity (lowest zipf = rarest)
        word_scores.sort(key=lambda x: x[1])

        # Determine max words based on corpus size
        if max_words is None:
            # Target: ~5-6 words per sentence on average
            # So we need roughly num_sentences * 5 unique words
            target_total = len(sentences) * 5
            # But also consider available rare words
            max_words = max(50, min(500, target_total))

        # Build result with rank
        result = {}
        for rank, (word, score) in enumerate(word_scores[:max_words]):
            result[word] = {
                "zipf": score,
                "rank": rank,  # 0 = rarest
                "count": word_counts[word],
                "sentences": word_sentences[word],
            }

        return result

    def get_rare_words_for_sentences(
        self,
        sentences: list[str],
        global_rare_words: dict[str, dict],
        min_per_sentence: int = 0,
        max_per_sentence: int = 6,
        target_avg: float = 5.0,
    ) -> list[list[tuple[str, float]]]:
        """
        Distribute rare words across sentences. Each word appears only once.

        Algorithm:
        1. Calculate target words per sentence based on sentence length
        2. Assign words to their FIRST occurrence sentence
        3. Prioritize rarer words (lower zipf)
        4. Short sentences get fewer words, long sentences get more

        Args:
            sentences: List of sentences
            global_rare_words: Output from extract_global_rare_words()
            min_per_sentence: Minimum words per sentence (0 = skip if no rare words)
            max_per_sentence: Maximum words per sentence
            target_avg: Target average words per sentence (default 5.0)

        Returns:
            List of lists, where each inner list is [(word, zipf), ...] for that sentence
        """
        # Calculate sentence lengths (word count)
        sentence_lengths = []
        for sentence in sentences:
            words = self.extract_words(sentence)
            valid_words = [w for w in words if len(w) >= 3 and w.lower() not in self.stopwords]
            sentence_lengths.append(len(valid_words))

        avg_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 1

        # Calculate target words per sentence (proportional to length)
        targets = []
        for length in sentence_lengths:
            if length == 0:
                targets.append(0)
            else:
                # Scale by sentence length relative to average
                ratio = length / avg_length
                target = int(round(target_avg * ratio))
                # Clamp to min/max
                target = max(min_per_sentence, min(max_per_sentence, target))
                targets.append(target)

        # Build word -> first sentence mapping
        # Sort words by rarity (lowest zipf first) to prioritize rare words
        sorted_words = sorted(
            global_rare_words.items(),
            key=lambda x: x[1]["zipf"]
        )

        # Assign words to sentences (each word only once, to first occurrence)
        result = [[] for _ in sentences]
        used_words = set()

        for word, info in sorted_words:
            # Find first sentence where this word appears
            first_sent = info["sentences"][0] if info["sentences"] else None
            if first_sent is None:
                continue

            # Check if sentence still needs words
            if len(result[first_sent]) < targets[first_sent]:
                result[first_sent].append((word, info["zipf"]))
                used_words.add(word)

        # Second pass: try to fill sentences that didn't get enough words
        # by checking other sentences where words appear
        for word, info in sorted_words:
            if word in used_words:
                continue

            # Try all sentences where this word appears
            for sent_idx in info["sentences"]:
                if len(result[sent_idx]) < targets[sent_idx]:
                    result[sent_idx].append((word, info["zipf"]))
                    used_words.add(word)
                    break

        # Sort words within each sentence by rarity
        for i in range(len(result)):
            result[i].sort(key=lambda x: x[1])

        return result

    def extract_words(self, text: str) -> list[str]:
        """Extract words from text."""
        # Remove punctuation and split
        words = re.findall(r'\b\w+\b', text.lower())
        return words

    def get_zipf_score(self, word: str) -> float:
        """
        Get Zipf frequency score for a word.

        Zipf scale: 1-7 (7 = most common like "the", 1 = very rare)
        Returns 0 if word not found.
        """
        if not WORDFREQ_AVAILABLE:
            # Fallback: longer words are rarer
            return max(1, 7 - len(word) * 0.5)

        # Use wordfreq_code (e.g. "es" for both "es" and "es-latam")
        return zipf_frequency(word, self._wordfreq_code)

    def is_rare(self, word: str) -> bool:
        """Check if word is considered rare."""
        if len(word) < 3:
            return False
        if word.lower() in self.stopwords:
            return False
        if word.isdigit():
            return False

        score = self.get_zipf_score(word)
        return score < self.zipf_threshold and score > 0

    def get_rare_words(
        self,
        sentence: str,
        max_words: int = 3,
        min_words: int = 2,
    ) -> list[tuple[str, float]]:
        """
        Get rarest words from sentence.

        Args:
            sentence: Input sentence
            max_words: Maximum number of rare words to return
            min_words: Minimum number of words to return (even if not rare)

        Returns:
            List of (word, zipf_score) tuples, sorted by rarity (rarest first)
        """
        words = self.extract_words(sentence)

        # Collect all valid words with scores
        all_word_scores = []
        rare_word_scores = []

        for word in words:
            if len(word) < 3:
                continue
            if word.lower() in self.stopwords:
                continue
            if word.isdigit():
                continue

            score = self.get_zipf_score(word)
            if score > 0:
                all_word_scores.append((word, score))
                if score < self.zipf_threshold:
                    rare_word_scores.append((word, score))

        # Sort by score (ascending = rarest first)
        rare_word_scores.sort(key=lambda x: x[1])
        all_word_scores.sort(key=lambda x: x[1])

        # Remove duplicates while preserving order
        def dedupe(word_scores):
            seen = set()
            unique = []
            for word, score in word_scores:
                if word.lower() not in seen:
                    seen.add(word.lower())
                    unique.append((word, score))
            return unique

        unique_rare = dedupe(rare_word_scores)

        # If we have enough rare words, return them
        if len(unique_rare) >= min_words:
            return unique_rare[:max_words]

        # Otherwise, fill with least common words (even if above threshold)
        unique_all = dedupe(all_word_scores)
        return unique_all[:max_words]


def get_rare_words(
    sentence: str,
    lang: str,
    max_words: int = 3,
    zipf_threshold: float = 4.5,
) -> list[str]:
    """
    Convenience function to get rare words from sentence.

    Args:
        sentence: Input sentence
        lang: Language code
        max_words: Maximum number of words
        zipf_threshold: Rarity threshold

    Returns:
        List of rare words (strings only)
    """
    analyzer = WordFrequencyAnalyzer(language=lang, zipf_threshold=zipf_threshold)
    rare = analyzer.get_rare_words(sentence, max_words)
    return [word for word, _ in rare]


def get_rare_words_with_translations(
    source_sentence: str,
    target_sentence: str,
    source_lang: str,
    target_lang: str,
    max_words: int = 5,
    zipf_threshold: float = 4.5,
    translator=None,
) -> list[tuple[str, str]]:
    """
    Get rare words from target sentence with translations to source language.
    Uses cached dictionary to avoid repeated API calls.

    Args:
        source_sentence: Sentence in source language
        target_sentence: Sentence in target language
        source_lang: Source language code
        target_lang: Target language code
        max_words: Maximum number of words to return
        zipf_threshold: Rarity threshold
        translator: Optional Translator instance for uncached words

    Returns:
        List of (target_word, source_translation) tuples
    """
    from .word_dictionary import get_dictionary

    # Get rare words from target (learner's target language)
    target_analyzer = WordFrequencyAnalyzer(language=target_lang, zipf_threshold=zipf_threshold)
    rare_target = target_analyzer.get_rare_words(target_sentence, max_words * 2)

    # Get dictionary (with cache)
    dictionary = get_dictionary()

    # Create translator if not provided (for uncached words)
    if translator is None:
        try:
            from core.translator import Translator
            translator = Translator()
        except ImportError:
            translator = None

    result = []
    for target_word, _ in rare_target:
        # Use dictionary (checks cache first, then translates if needed)
        translation = dictionary.translate(target_word, target_lang, source_lang, translator)
        result.append((target_word, translation))

        if len(result) >= max_words:
            break

    return result
