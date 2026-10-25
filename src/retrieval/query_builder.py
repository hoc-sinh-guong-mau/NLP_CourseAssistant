def build_query(frame):
    if (frame.predicate, frame.qtype) != ("GET_DEADLINE", "DEADLINE"):
        raise ValueError("Unsupported predicate")
    return {
        "collection": "assignments",
        "filters": {"id": frame.arguments["assignment_id"]},
        "select": ["deadline"],
    }
