"""Language constants and utilities.

Centralizes all language codes to avoid confusion between:
- es (European Spanish) vs es-latam (Latin American/Argentine Spanish)
- Different provider naming conventions

IMPORTANT: Unsupported languages raise UnsupportedLanguageError - never silently ignored!
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Language:
    """Language definition with all naming variants."""
    code: str           # Internal code used in project
    name: str           # Human-readable name
    name_ru: str        # Russian name
    tts_code: str       # Google Cloud TTS language code
    wordfreq_code: str  # wordfreq library code


# === Language Constants ===

RUSSIAN = Language(
    code="ru",
    name="Russian",
    name_ru="Русский",
    tts_code="ru-RU",
    wordfreq_code="ru",
)

ENGLISH = Language(
    code="en",
    name="English",
    name_ru="Английский",
    tts_code="en-US",
    wordfreq_code="en",
)

ENGLISH_GB = Language(
    code="en-GB",
    name="British English",
    name_ru="Британский английский",
    tts_code="en-GB",
    wordfreq_code="en",
)

# European Spanish (Spain) - uses "tú", "vosotros"
SPANISH = Language(
    code="es",
    name="Spanish (Spain)",
    name_ru="Испанский (Испания)",
    tts_code="es-ES",
    wordfreq_code="es",
)

# Latin American Spanish (Argentine/Rioplatense) - uses "vos", "ustedes"
SPANISH_LATAM = Language(
    code="es-latam",
    name="Spanish (Latin America)",
    name_ru="Испанский (Латинская Америка)",
    tts_code="es-US",  # Google uses es-US for LatAm
    wordfreq_code="es",  # wordfreq doesn't distinguish
)

PORTUGUESE_BR = Language(
    code="pt-BR",
    name="Portuguese (Brazil)",
    name_ru="Португальский (Бразилия)",
    tts_code="pt-BR",
    wordfreq_code="pt",
)

GERMAN = Language(
    code="de",
    name="German",
    name_ru="Немецкий",
    tts_code="de-DE",
    wordfreq_code="de",
)

FRENCH = Language(
    code="fr",
    name="French",
    name_ru="Французский",
    tts_code="fr-FR",
    wordfreq_code="fr",
)


# === Registry ===

# All supported languages
ALL_LANGUAGES = [
    RUSSIAN,
    ENGLISH,
    ENGLISH_GB,
    SPANISH,
    SPANISH_LATAM,
    PORTUGUESE_BR,
    GERMAN,
    FRENCH,
]

# Lookup by code (including aliases)
_LANGUAGE_MAP = {lang.code: lang for lang in ALL_LANGUAGES}

# Aliases for common variations
_ALIASES = {
    "es-ar": SPANISH_LATAM,
    "es-419": SPANISH_LATAM,  # UN M.49 code for Latin America
    "es-US": SPANISH_LATAM,
    "es-ES": SPANISH,
    "en-US": ENGLISH,
    "ru-RU": RUSSIAN,
    "pt": PORTUGUESE_BR,
}


def get_language(code: str) -> Optional[Language]:
    """Get Language by code or alias.

    Examples:
        get_language("ru") -> RUSSIAN
        get_language("es-latam") -> SPANISH_LATAM
        get_language("es-ar") -> SPANISH_LATAM (alias)
    """
    code_lower = code.lower()

    # Try direct match
    if code_lower in _LANGUAGE_MAP:
        return _LANGUAGE_MAP[code_lower]

    # Try aliases
    if code_lower in _ALIASES:
        return _ALIASES[code_lower]

    # Try case-insensitive match
    for lang in ALL_LANGUAGES:
        if lang.code.lower() == code_lower:
            return lang

    return None


def normalize_code(code: str) -> str:
    """Normalize language code to internal format.

    Examples:
        normalize_code("es-AR") -> "es-latam"
        normalize_code("ES") -> "es"
        normalize_code("ru-RU") -> "ru"
    """
    lang = get_language(code)
    return lang.code if lang else code.lower()


def is_spanish(code: str) -> bool:
    """Check if code is any Spanish variant."""
    lang = get_language(code)
    return lang in (SPANISH, SPANISH_LATAM) if lang else code.lower().startswith("es")


def is_latam_spanish(code: str) -> bool:
    """Check if code is Latin American Spanish."""
    lang = get_language(code)
    return lang == SPANISH_LATAM


def get_wordfreq_code(code: str) -> str:
    """Get wordfreq library code for language.

    wordfreq doesn't distinguish regional variants.
    """
    lang = get_language(code)
    return lang.wordfreq_code if lang else code.split("-")[0].lower()


def get_tts_code(code: str) -> str:
    """Get Google Cloud TTS language code."""
    lang = get_language(code)
    return lang.tts_code if lang else code


# === Validation (MUST be after ALL_LANGUAGES) ===

class UnsupportedLanguageError(ValueError):
    """Raised when an unsupported language code is used.

    Use this to fail fast - never silently ignore wrong language codes!
    """

    def __init__(self, code: str, context: str = ""):
        self.code = code
        self.context = context
        supported = ", ".join(lang.code for lang in ALL_LANGUAGES)
        message = f"Unsupported language code: '{code}'"
        if context:
            message += f" in {context}"
        message += f". Supported: {supported}"
        super().__init__(message)


def require_language(code: str, context: str = "") -> Language:
    """Get Language by code, raising error if not found.

    Use this instead of get_language() when unsupported language should fail.

    Args:
        code: Language code to look up
        context: Context for error message (e.g. "TextSplitter", "TTS provider")

    Returns:
        Language object

    Raises:
        UnsupportedLanguageError: If language code is not supported
    """
    lang = get_language(code)
    if lang is None:
        raise UnsupportedLanguageError(code, context)
    return lang


def validate_language(code: str, context: str = "") -> str:
    """Validate and normalize language code, raising error if invalid.

    Args:
        code: Language code to validate
        context: Context for error message

    Returns:
        Normalized language code

    Raises:
        UnsupportedLanguageError: If language code is not supported
    """
    lang = require_language(code, context)
    return lang.code


def is_supported(code: str) -> bool:
    """Check if language code is supported (without raising)."""
    return get_language(code) is not None
