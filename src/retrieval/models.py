"""Query registry contracts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class QuerySpec:
    collection: str
    filters: tuple[tuple[str, str], ...]  # (KB field, semantic argument)
    select: tuple[str, ...]


