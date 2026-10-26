"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class GrammarError(NLPError):
    stage = 'grammar'
    code = 'GRAMMAR_INVALID'


class ParseError(NLPError):
    stage = 'parsing'
    code = 'PARSE_FAILED'
    status = 'parse_failed'


class AmbiguousParseError(ParseError):
    stage = 'parsing'
    code = 'PARSE_AMBIGUOUS'
    status = 'ambiguous'


class GenerationError(NLPError):
    stage = 'sentence_generation'
    code = 'GENERATION_INVALID'


class ParseInputError(NLPError):
    stage = 'parsing'
    code = 'PARSE_INPUT_INVALID'
