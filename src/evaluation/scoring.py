"""Observable comparisons; answer text checks never infer KB facts from prose."""
import json
import unicodedata


def entity_pairs(entities):
    return {(slot, value) for slot, values in entities.items()
            for value in (values if isinstance(values, list) else [values])}


def labels(expected):
    result = dict(expected.get('intent_entity') or {})
    semantic = expected.get('semantic') or {}
    if semantic:
        result.update(intent=semantic['predicate'], qtype=semantic['qtype'], entities=semantic['arguments'])
    result.update({key: expected[key] for key in ('intent', 'qtype', 'entities') if key in expected})
    # Explicit null denotes no recognized request, without adding grammar UNKNOWN rules.
    if expected.get('intent_entity', False) is None or expected.get('semantic', False) is None:
        result = {'intent': 'UNKNOWN', 'qtype': 'UNKNOWN', 'entities': {}, **result}
    return result


def actual_labels(actual):
    frame = actual.get('intent_entity') or {}
    return {'intent': frame.get('intent') or 'UNKNOWN',
            'qtype': frame.get('qtype') or 'UNKNOWN', 'entities': frame.get('entities') or {}}


def contains(actual, expected):
    if isinstance(expected, dict):
        if not expected:
            return actual == {}
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value)
                                                for key, value in expected.items())
    return actual == expected


def query_key(query):
    if query is None:
        return None
    result = dict(query)
    # Projection order and conjunction order do not change the logical query.
    for key in ('select', 'conditions'):
        if isinstance(result.get(key), list):
            result[key] = sorted(result[key], key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return result


def text_key(text):
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())


def score_turn(expected, actual):
    checks = {}
    predicted = actual_labels(actual)
    for key, value in expected.items():
        observed = predicted[key] if key in predicted else actual.get(key)
        if key == 'entities':
            correct = entity_pairs(observed) == entity_pairs(value)
        elif key == 'query':
            correct = query_key(observed) == query_key(value)
        elif key in {'context_used', 'context_after'}:
            correct = contains(observed, value)
        elif key in {'answer_contains', 'answer_not_contains'}:
            observed = actual.get('answer') or ''
            present = [text_key(fragment) in text_key(observed) for fragment in value]
            correct = all(present) if key == 'answer_contains' else not any(present)
        elif key == 'result_contains':
            observed = actual.get('result') or []
            correct = all(any(contains(row, fact) for row in observed) for fact in value)
        else:
            correct = observed == value
        checks[key] = {'correct': correct, 'expected': value, 'actual': observed}
    return {'correct': all(check['correct'] for check in checks.values()),
            'checks': checks, 'expected_labels': labels(expected),
            'actual_labels': predicted, 'actual': actual}
