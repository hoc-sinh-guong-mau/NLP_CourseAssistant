"""Declarative query registry: add a spec without editing pipeline control flow."""
from dataclasses import dataclass


class UnsupportedQueryError(ValueError):
    """The semantic frame is valid, but has no query implementation yet."""


@dataclass(frozen=True)
class QuerySpec:
    collection: str
    filters: tuple[tuple[str, str], ...]  # (KB field, semantic argument)
    select: tuple[str, ...]


QUERY_SPECS = {
    ("GET_DEADLINE", "DEADLINE"): QuerySpec(
        collection="assignments",
        filters=(("id", "assignment_id"),),
        select=("deadline",),
    ),
}


class QueryBuilder:
    def __init__(self, specs=None):
        self.specs = dict(QUERY_SPECS if specs is None else specs)

    def build(self, frame):
        key = (frame.predicate, frame.qtype)
        if key not in self.specs:
            raise UnsupportedQueryError(f"Unsupported query: {key}")
        spec = self.specs[key]
        return {
            "collection": spec.collection,
            "filters": {field: frame.arguments[slot] for field, slot in spec.filters},
            "select": list(spec.select),
        }


def build_query(frame):
    return QueryBuilder().build(frame)
