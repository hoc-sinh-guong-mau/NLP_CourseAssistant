"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class SemanticError(NLPError):
    stage = 'semantic'
    code = 'SEMANTIC_ERROR'


class UnsupportedSemanticError(SemanticError):
    stage = 'semantic'
    code = 'SEMANTIC_UNSUPPORTED'
    status = 'unsupported_semantic'


class InvalidSemanticError(SemanticError):
    stage = 'semantic'
    code = 'SEMANTIC_INVALID'
    status = 'invalid_semantic'
