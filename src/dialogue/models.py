"""Bounded per-session context; references come from structured KB entities."""
from dataclasses import dataclass, field, asdict


@dataclass
class ContextState:
    entities: dict[str, list[str]] = field(default_factory=dict)
    focus: str | None = None
    source_turn: int | None = None

    def to_dict(self):
        return asdict(self)
