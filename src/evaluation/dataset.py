"""Load labeled single-turn and dialogue cases before executing any NLP stage."""
import json
from pathlib import Path

from src.common.files import read_text
from .exceptions import EvaluationError

LABEL_FIELDS = {'intent', 'qtype', 'entities'}
RECORD_FIELDS = {'status', 'semantic', 'intent_entity', 'query', 'answer', 'parse_tree',
                 'parse_count', 'statistical_used', 'statistical_attempted'}
CHECK_FIELDS = LABEL_FIELDS | RECORD_FIELDS | {
    'answer_contains', 'answer_not_contains', 'result_contains', 'context_used', 'context_after',
}


def _invalid(message, **context):
    raise EvaluationError(message, context=context)


def _validate_expected(expected, *, case_id, turn):
    context = {'case': case_id, 'turn': turn}
    if not isinstance(expected, dict) or not expected:
        _invalid('Expected labels must be a nonempty mapping', **context)
    unknown = set(expected) - CHECK_FIELDS
    if unknown:
        _invalid(f'Unsupported expected fields: {sorted(unknown)}', **context)
    for key, value in expected.items():
        if key in {'intent', 'qtype', 'status', 'answer', 'parse_tree'}:
            if not isinstance(value, str) or not value.strip():
                _invalid(f'{key} must be a nonempty string', **context)
        elif key in {'statistical_used', 'statistical_attempted'}:
            if not isinstance(value, bool):
                _invalid(f'{key} must be boolean', **context)
        elif key == 'parse_count':
            if type(value) is not int or value < 0:
                _invalid('parse_count must be a nonnegative integer', **context)
        elif key in {'answer_contains', 'answer_not_contains'}:
            if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v.strip() for v in value):
                _invalid(f'{key} must be a nonempty list of nonempty strings', **context)
        elif key == 'result_contains':
            if not isinstance(value, list) or not value or any(not isinstance(v, dict) or not v for v in value):
                _invalid('result_contains must contain nonempty row mappings', **context)
        elif key in {'entities', 'context_used', 'context_after'}:
            if not isinstance(value, dict):
                _invalid(f'{key} must be a mapping', **context)
            if key == 'entities':
                for slot, ids in value.items():
                    values = ids if isinstance(ids, list) else [ids]
                    if not slot or not values or any(not isinstance(v, str) or not v for v in values):
                        _invalid('Entity slots require canonical IDs or nonempty ID lists', **context)
        elif value is not None and not isinstance(value, dict):
            _invalid(f'{key} must be a mapping or null', **context)
    labels = expected.get('intent_entity')
    if labels is not None:
        if set(labels) != {'intent', 'qtype', 'entities'}:
            _invalid('intent_entity requires intent, qtype and entities', **context)
        _validate_expected(labels, case_id=case_id, turn=turn)
        for key in LABEL_FIELDS & expected.keys():
            if expected[key] != labels[key]:
                _invalid(f'Conflicting {key} and intent_entity labels', **context)
    semantic = expected.get('semantic')
    if semantic is not None:
        if set(semantic) != {'predicate', 'qtype', 'arguments'}:
            _invalid('semantic requires predicate, qtype and arguments', **context)
        semantic_labels = {'intent': semantic['predicate'], 'qtype': semantic['qtype'], 'entities': semantic['arguments']}
        _validate_expected(semantic_labels, case_id=case_id, turn=turn)
        for key, value in semantic_labels.items():
            if key in expected and expected[key] != value:
                _invalid(f'Conflicting {key} and semantic labels', **context)
            if labels is not None and labels[key] != value:
                _invalid('Conflicting semantic and intent_entity labels', **context)


def load_cases(path):
    """Legacy {input, expected} lines remain supported; blanks are ignored."""
    path = Path(path)
    cases, seen = [], set()
    for line_number, line in enumerate(read_text(path, EvaluationError, encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, parse_constant=lambda value: _invalid(
                f'Non-finite JSON number: {value}', line=line_number))
        except json.JSONDecodeError as exc:
            raise EvaluationError('Invalid evaluation JSON', context={'path': str(path), 'line': line_number}) from exc
        if not isinstance(row, dict):
            _invalid('Evaluation case must be a mapping', line=line_number)
        if set(row) - {'id', 'tags', 'input', 'expected', 'turns', 'description'}:
            _invalid('Unknown evaluation case fields', line=line_number)
        case_id = row.get('id', f'case_{line_number:03}')
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            _invalid('Case IDs must be nonempty and unique', line=line_number)
        seen.add(case_id)
        tags = row.get('tags', [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            _invalid('tags must be a list of nonempty strings', case=case_id)
        if 'turns' in row:
            if 'input' in row or 'expected' in row:
                _invalid('Use turns or input/expected, never both', case=case_id)
            turns = row['turns']
            if not isinstance(turns, list) or not turns:
                _invalid('Dialogue turns must be a nonempty list', case=case_id)
        else:
            turns = [{'input': row.get('input'), 'expected': row.get('expected')}]
        for number, turn in enumerate(turns, 1):
            if not isinstance(turn, dict) or set(turn) != {'input', 'expected'}:
                _invalid('Each turn requires exactly input and expected', case=case_id, turn=number)
            if not isinstance(turn['input'], str) or not turn['input'].strip():
                _invalid('Evaluation input must be a nonempty string', case=case_id, turn=number)
            _validate_expected(turn['expected'], case_id=case_id, turn=number)
        cases.append({'id': case_id, 'tags': list(dict.fromkeys(tags)),
                      'dialogue': 'turns' in row, 'turns': turns})
    if not cases:
        _invalid('Evaluation dataset must not be empty', path=str(path))
    return cases
