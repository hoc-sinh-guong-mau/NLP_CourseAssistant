import re
import unicodedata

from .exceptions import PreprocessingError


def normalize(text: str) -> str:
    if not isinstance(text, str):
        raise PreprocessingError("text must be a string")
    text = unicodedata.normalize("NFC", text).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    # Normalize LO codes before handling sentence-final punctuation.
    text = re.sub(
        r"\bl\s*\.\s*o\s*\.\s*(\d+(?:\.\d+)*)\b",
        r"lo\1",
        text,
    )
    # Drop only sentence-final ?, !, . (including spaced repetitions).
    # Decimal/code dots inside tokens, commas, slashes and hyphens survive.
    text = re.sub(r"[?!.\s]+$", "", text)
    return unicodedata.normalize("NFC", text)

def tokenize(normalized_text: str) -> list[str]:
    if not isinstance(normalized_text, str):
        raise PreprocessingError("normalized_text must be a string")
    return normalized_text.split()
