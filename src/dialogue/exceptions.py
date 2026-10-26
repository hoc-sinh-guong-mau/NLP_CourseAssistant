from src.common import NLPError


class ContextResolutionError(NLPError):
    stage = 'dialogue'
    code = 'CONTEXT_UNRESOLVED'
    status = 'needs_context'
