"""Project an interpreted request into the intent/entity output contract."""
from copy import deepcopy
from typing import Any

from .models import SemanticFrame


def extract(frame: SemanticFrame) -> dict[str, Any]:
    """Preserve semantic roles without sharing mutable slots with the frame.

    Recognition is performed by grammar unification and the interpreter;
    this step formats that result rather than guessing again from keywords.
    """
    return {
        "intent": frame.predicate,
        "qtype": frame.qtype,
        "entities": deepcopy(frame.arguments),
    }
