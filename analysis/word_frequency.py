"""Word frequency analysis for identifying rare words."""

import re
from typing import Optional

try:
    from wordfreq import zipf_frequency
    WORDFREQ_AVAILABLE = True
except ImportError:
    WORDFREQ_AVAILABLE = False


# Common stopwords to skip (very basic list)
STOPWORDS = {
    "ru": {"и", "в", "на", "с", "по", "за", "к", "от", "из", "у", "о", "а", "но", "что", "как", "это", "он", "она", "они", "мы", "вы", "я", "ты", "не", "да", "же", "бы", "ли", "то", "так", "все", "для", "до", "при", "его", "её", "их", "мой", "твой", "наш", "ваш", "свой", "этот", "тот", "такой", "который", "когда", "где", "если", "чтобы", "потому", "только", "уже", "ещё", "очень", "можно", "нужно", "быть", "есть", "был", "была", "были", "будет"},
    "en": {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "and", "but", "if", "or", "because", "until", "while", "it", "its", "this", "that", "these", "those", "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "am"},
    "es": {"el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "de", "del", "en", "con", "por", "para", "a", "al", "que", "es", "son", "está", "están", "fue", "fueron", "ser", "estar", "tener", "hacer", "como", "pero", "más", "ya", "muy", "también", "solo", "sin", "sobre", "entre", "hasta", "desde", "durante", "si", "no", "sí", "yo", "tú", "él", "ella", "nosotros", "vosotros", "ellos", "ellas", "mi", "tu", "su", "nuestro", "vuestro", "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas", "qué", "quién", "cuál", "cuándo", "dónde", "cómo", "cuánto", "hay", "había", "ha", "han", "he", "hemos", "me", "te", "se", "le", "les", "lo", "nos", "os"},
}


class WordFrequencyAnalyzer:
    """Analyzes word frequency to identify rare words."""

    def __init__(self, language: str = "en", zipf_threshold: float = 4.5):
        """
        Initialize analyzer.

        Args:
            language: Language code (ru, en, es)
            zipf_threshold: Zipf score threshold (lower = rarer, 1-7 scale)
                           Words with score below this are considered rare
        """
        self.language = language
        self.zipf_threshold = zipf_threshold
        self.stopwords = STOPWORDS.get(language, set())

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

        return zipf_frequency(word, self.language)

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
    ) -> list[tuple[str, float]]:
        """
        Get rarest words from sentence.

        Args:
            sentence: Input sentence
            max_words: Maximum number of rare words to return

        Returns:
            List of (word, zipf_score) tuples, sorted by rarity (rarest first)
        """
        words = self.extract_words(sentence)
        word_scores = []

        for word in words:
            if len(word) < 3:
                continue
            if word.lower() in self.stopwords:
                continue
            if word.isdigit():
                continue

            score = self.get_zipf_score(word)
            if 0 < score < self.zipf_threshold:
                word_scores.append((word, score))

        # Sort by score (ascending = rarest first)
        word_scores.sort(key=lambda x: x[1])

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for word, score in word_scores:
            if word.lower() not in seen:
                seen.add(word.lower())
                unique.append((word, score))

        return unique[:max_words]


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
