"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class AnswerError(NLPError):
    stage = 'generation'
    code = 'ANSWER_INVALID'


class UnsupportedAnswerError(AnswerError):
    stage = 'generation'
    code = 'ANSWER_UNSUPPORTED'
    status = 'unsupported_answer'
