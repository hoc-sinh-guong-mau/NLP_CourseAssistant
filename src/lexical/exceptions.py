"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class LexiconError(NLPError):
    stage = 'lexical'
    code = 'LEXICON_INVALID'
