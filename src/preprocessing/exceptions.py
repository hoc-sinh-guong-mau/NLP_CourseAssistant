"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class PreprocessingError(NLPError):
    stage = 'preprocessing'
    code = 'INPUT_INVALID'
