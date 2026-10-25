from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SemanticFrame:
    predicate: str
    arguments: dict[str, Any]
    qtype: str

    def to_dict(self):
        return asdict(self)


def interpret(tree):
    features = tree.label()
    intent, entity, qtype = (features.get(key) for key in ("INTENT", "ENTITY", "QTYPE"))
    if not all(isinstance(value, str) for value in (intent, entity, qtype)):
        raise ValueError("Missing or unresolved semantic features")
    if (intent, qtype) == ("GET_DEADLINE", "DEADLINE"):
        arguments = {"assignment_id": entity}
    elif (intent, qtype) == ("GET_SCHEDULE", "WEEK_CONTENT"):
        arguments = {"week_id": entity}
    else:
        # Preserve the grammar's entity role; query handlers can specialize later.
        arguments = {"entity": entity}
    target = features.get("TARGET", "NONE")
    if not isinstance(target, str):
        raise ValueError("Unresolved TARGET feature")
    if target != "NONE":
        arguments["target"] = target
    return SemanticFrame(intent, arguments, qtype)
