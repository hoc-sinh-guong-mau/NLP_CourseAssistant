def extract(frame):
    """Derive intent/entities from the semantic frame produced by the parse tree."""
    return {"intent": frame.predicate, "qtype": frame.qtype, "entities": dict(frame.arguments)}
