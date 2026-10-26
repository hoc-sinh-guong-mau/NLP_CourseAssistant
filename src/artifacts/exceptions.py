"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class ArtifactError(NLPError):
    stage = 'artifacts'
    code = 'ARTIFACT_IO_FAILED'
