"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class EvaluationError(NLPError):
    stage = 'evaluation'
    code = 'EVALUATION_INVALID'
