"""Declarative query registry: add a spec without editing pipeline control flow."""
from .exceptions import QueryError, UnsupportedQueryError
from .models import QuerySpec


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
        missing = [slot for _, slot in spec.filters if slot not in frame.arguments]
        if missing:
            raise QueryError("Missing semantic arguments", context={"slots": missing, "intent": frame.predicate, "qtype": frame.qtype})
        return {
            "collection": spec.collection,
            "filters": {field: frame.arguments[slot] for field, slot in spec.filters},
            "select": list(spec.select),
        }

