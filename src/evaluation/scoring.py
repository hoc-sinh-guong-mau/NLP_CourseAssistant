"""Label projection and observable checks, without guessing missing annotations."""

import unicodedata

ABSTENTION_STATUSES = {
    "missing_information",
    "unsupported_query",
    "unsupported_semantic",
    "unsupported_answer",
    "parse_failed",
    "invalid_semantic",
    "needs_context",
    "ambiguous",
}
LABEL_FIELDS = ("intent", "qtype", "entities")


def abstained(record):
    return (
        record.get("abstained") is True or record.get("status") in ABSTENTION_STATUSES
    )


def expected_abstention(expected):
    if "abstain" in expected:
        return expected["abstain"]
    status = expected.get("status")
    if status == "ok":
        return False
    return True if isinstance(status, str) and status in ABSTENTION_STATUSES else None


def _label_sources(expected):
    sources = [expected.get("intent_entity") or {}]
    semantic = expected.get("semantic") or {}
    sources.append(
        {
            target: semantic[source]
            for source, target in (
                ("predicate", "intent"),
                ("qtype", "qtype"),
                ("arguments", "entities"),
            )
            if source in semantic
        }
    )
    sources.append({key: expected[key] for key in LABEL_FIELDS if key in expected})
    return sources


def label_conflicts(expected):
    conflicts = []
    for key in LABEL_FIELDS:
        values = [source[key] for source in _label_sources(expected) if key in source]
        if values and any(value != values[0] for value in values[1:]):
            conflicts.append(key)
    return conflicts


def gold_labels(expected):
    labels = {}
    for source in _label_sources(expected):
        labels.update(source)
    # Keep contradictory gold visible in raw exact-match checks; don't select one as metric truth.
    conflicts = set(label_conflicts(expected))
    for key in conflicts:
        labels.pop(key, None)
    if (
        "entities" not in labels
        and "entities" not in conflicts
        and any(
            key in expected and expected[key] is None
            for key in ("semantic", "intent_entity")
        )
    ):
        labels["entities"] = None
    return labels


def actual_labels(actual):
    frame = actual.get("semantic") or {}
    intent_entity = actual.get("intent_entity") or {}
    return {
        "intent": intent_entity.get("intent", frame.get("predicate")),
        "qtype": intent_entity.get("qtype", frame.get("qtype")),
        "entities": frame.get("arguments", intent_entity.get("entities")),
    }


def entity_pairs(entities):
    return {
        (slot, value)
        for slot, values in (entities or {}).items()
        for value in (values if isinstance(values, list) else [values])
    }


def contains(actual, expected):
    if isinstance(expected, dict):
        if not expected:
            return actual == {}
        return isinstance(actual, dict) and all(
            key in actual and contains(actual[key], value)
            for key, value in expected.items()
        )
    return actual == expected


def _text(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def score(expected, actual):
    checks = {}
    predicted = actual_labels(actual)
    for key, value in expected.items():
        if key == "abstain":
            correct = abstained(actual) == value
        elif key == "entities":
            correct = (predicted[key] or {}) == value
        elif key in LABEL_FIELDS:
            correct = predicted[key] == value
        elif key in ("context_used", "context_after"):
            correct = contains(actual.get(key), value)
        elif key in ("answer_contains", "answer_not_contains"):
            matches = [
                _text(fragment) in _text(actual.get("answer") or "")
                for fragment in value
            ]
            correct = all(matches) if key == "answer_contains" else not any(matches)
        elif key == "result_contains":
            correct = all(
                any(contains(row, fact) for row in (actual.get("result") or []))
                for fact in value
            )
        else:
            # Legacy exact match is deliberately unchanged, including query and answer strings.
            correct = actual.get(key) == value
        checks[key] = correct
    return {
        "correct": all(checks.values()),
        "expected": expected,
        "checks": checks,
        "actual_abstained": abstained(actual),
        "actual": actual,
    }
