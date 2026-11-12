"""Metrics with explicit denominators; unannotated components are not scored."""
from collections import Counter
from math import ceil
from statistics import median

from .scoring import entity_pairs


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def accuracy(values):
    values = list(values)
    return {'total': len(values), 'correct': sum(values), 'accuracy': ratio(sum(values), len(values))}


def classification(rows, field):
    pairs = [(row['expected_labels'][field], row['actual_labels'][field])
             for row in rows if field in row['expected_labels']]
    gold = Counter(truth for truth, _ in pairs)
    predicted = Counter(guess for _, guess in pairs)
    correct = Counter(truth for truth, guess in pairs if truth == guess)
    per_label = {}
    for label in sorted(gold.keys() | predicted.keys()):
        tp = correct[label]
        per_label[label] = {'support': gold[label], 'predicted': predicted[label],
                            'precision': tp / predicted[label] if predicted[label] else 0.0,
                            'recall': tp / gold[label] if gold[label] else 0.0,
                            'f1': 2 * tp / (gold[label] + predicted[label])}
    confusion = Counter(pairs)
    return {**accuracy(truth == guess for truth, guess in pairs),
            'macro_f1': ratio(sum(per_label[label]['f1'] for label in gold), len(gold)),
            'macro_labels': 'labels_with_gold_support', 'per_label': per_label,
            'confusion': [{'expected': truth, 'predicted': guess, 'count': count}
                          for (truth, guess), count in sorted(confusion.items())]}


def entity_metrics(rows):
    tp = fp = fn = 0
    exact = []
    for row in rows:
        if 'entities' not in row['expected_labels']:
            continue
        gold = entity_pairs(row['expected_labels']['entities'])
        predicted = entity_pairs(row['actual_labels']['entities'])
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        exact.append(gold == predicted)
    return {'exact_match': accuracy(exact), 'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
            'micro_precision': ratio(tp, tp + fp), 'micro_recall': ratio(tp, tp + fn),
            'micro_f1': ratio(2 * tp, 2 * tp + fp + fn)}


def _checks(rows, fields):
    for row in rows:
        checks = [row['checks'][field]['correct'] for field in fields if field in row['checks']]
        if checks:
            yield all(checks)


def _semantic_frames(rows):
    for row in rows:
        gold = row['expected_labels']
        if not {'intent', 'qtype', 'entities'} <= gold.keys():
            continue
        frame = row['actual'].get('semantic')
        if gold['intent'] == 'UNKNOWN':
            yield frame is None
        else:
            yield bool(frame and frame.get('predicate') == gold['intent']
                       and frame.get('qtype') == gold['qtype']
                       and entity_pairs(frame.get('arguments', {})) == entity_pairs(gold['entities']))


def summarize(cases):
    rows = [row for case in cases for row in case['turns']]
    attempted = [row for row in rows if row['actual'].get('statistical_attempted')
                 or row['actual'].get('statistical_prediction') is not None]
    accepted = [row for row in rows if row['actual'].get('statistical_used')]
    labeled_accepted = [row for row in accepted if {'intent', 'qtype', 'entities'} <= row['expected_labels'].keys()]
    unknown = [row for row in rows if row['expected_labels'].get('intent') == 'UNKNOWN']
    false_accepts = sum(row['actual_labels']['intent'] != 'UNKNOWN' for row in unknown)
    latencies = sorted(row['elapsed_ms'] for row in rows)
    groups = {}
    for tag in sorted({tag for case in cases for tag in case['tags']}):
        group = [case for case in cases if tag in case['tags']]
        groups[tag] = {'cases': accuracy(case['correct'] for case in group),
                       'turns': accuracy(row['correct'] for case in group for row in case['turns'])}
    return {
        'case_accuracy': accuracy(case['correct'] for case in cases),
        'turn_accuracy': accuracy(row['correct'] for row in rows),
        'parser': {'parsed_turns': sum(row['actual'].get('parse_tree', '()') != '()' for row in rows),
                   'total_turns': len(rows),
                   'parse_rate': ratio(sum(row['actual'].get('parse_tree', '()') != '()' for row in rows), len(rows))},
        'intent': classification(rows, 'intent'), 'qtype': classification(rows, 'qtype'),
        'entities': entity_metrics(rows),
        'semantic_exact_match': accuracy(_checks(rows, ('semantic',))),
        'semantic_frame_accuracy': accuracy(_semantic_frames(rows)),
        'query_exact_match': accuracy(_checks(rows, ('query',))),
        'status': accuracy(_checks(rows, ('status',))),
        'retrieved_facts': accuracy(_checks(rows, ('result_contains',))),
        'answer': accuracy(_checks(rows, ('answer', 'answer_contains', 'answer_not_contains'))),
        'dialogue': {'session_accuracy': accuracy(case['correct'] for case in cases if case['dialogue']),
                     'reference_accuracy': accuracy(_checks(rows, ('context_used',)))},
        'fallback': {'attempted': len(attempted), 'accepted': len(accepted),
                     'acceptance_rate': ratio(len(accepted), len(attempted)),
                     'accepted_case_checks': accuracy(row['correct'] for row in accepted),
                     'accepted_semantic_accuracy': accuracy(
                         row['expected_labels'] == row['actual_labels'] for row in labeled_accepted)},
        'unknown_requests': {'total': len(unknown), 'false_accepts': false_accepts,
                             'false_acceptance_rate': ratio(false_accepts, len(unknown))},
        'latency_ms': {'count': len(latencies), 'median': median(latencies) if latencies else None,
                       'p95': latencies[ceil(len(latencies) * 0.95) - 1] if latencies else None,
                       'note': 'Warm process timings; model/grammar startup excluded; not a load benchmark.'},
        'groups': groups,
    }


def compare_cases(baseline, hybrid):
    baseline_turns = [row for case in baseline for row in case['turns']]
    hybrid_turns = [row for case in hybrid for row in case['turns']]
    recovered = regressed = accepted_wrong = 0
    for before, after in zip(baseline_turns, hybrid_turns):
        recovered += not before['correct'] and after['correct']
        regressed += before['correct'] and not after['correct']
        accepted_wrong += bool(after['actual'].get('statistical_used')) and not after['correct']
    return {'evaluated_turns': len(hybrid_turns), 'recovered_turns': recovered,
            'regressed_turns': regressed, 'fallback_accepted_incorrect_turns': accepted_wrong,
            'turn_accuracy_delta': (sum(row['correct'] for row in hybrid_turns)
                                    - sum(row['correct'] for row in baseline_turns)) / len(hybrid_turns)}
