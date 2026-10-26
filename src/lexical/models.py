"""Domain lexical data contracts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    category: str
    aliases: tuple[str, ...]
    canonical_id: str | None = None
    entity_type: str | None = None
