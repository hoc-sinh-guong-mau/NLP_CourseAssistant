"""Task metrics and the existing N1–N5 abstention convention."""

from collections import Counter
from math import ceil
from statistics import median


def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _intent_metrics(truth, predictions):
    if len(truth) != len(predictions):
        raise ValueError(
            "Classification labels and predictions must have the same length"
        )
    labels = sorted(set(truth) | set(predictions))
    matrix = {actual: {predicted: 0 for predicted in labels} for actual in labels}
    per_class = {}
    for actual, predicted in zip(truth, predictions):
        matrix[actual][predicted] += 1

    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in labels if other != label)
        fn = sum(matrix[label][other] for other in labels if other != label)
        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": _safe_divide(2 * precision * recall, precision + recall),
            "support": sum(matrix[label].values()),
        }

    count = len(truth)
    macro = {
        metric: _safe_divide(
            sum(scores[metric] for scores in per_class.values()), len(labels)
        )
        for metric in ("precision", "recall", "f1")
    }
    return {
        "count": count,
        "accuracy": _safe_divide(
            sum(a == p for a, p in zip(truth, predictions)), count
        ),
        "precision": _safe_divide(
            sum(s["precision"] * s["support"] for s in per_class.values()), count
        ),
        "recall": _safe_divide(
            sum(s["recall"] * s["support"] for s in per_class.values()), count
        ),
        "f1": _safe_divide(
            sum(s["f1"] * s["support"] for s in per_class.values()), count
        ),
        "macro_f1": macro["f1"],
        "per_class": per_class,
        "confusion_matrix": {"labels": labels, "counts": matrix},
    }


def _abstention_metrics(should_abstain, abstained, task_correct):
    """Compute the survey's five-outcome abstention confusion matrix."""
    if not len(should_abstain) == len(abstained) == len(task_correct):
        raise ValueError("Abstention inputs must have the same length")
    n1 = sum(
        not required and not did_abstain and correct
        for required, did_abstain, correct in zip(
            should_abstain, abstained, task_correct
        )
    )
    n2 = sum(
        not required and not did_abstain and not correct
        for required, did_abstain, correct in zip(
            should_abstain, abstained, task_correct
        )
    )
    n3 = sum(
        not required and did_abstain
        for required, did_abstain in zip(should_abstain, abstained)
    )
    n4 = sum(
        required and not did_abstain
        for required, did_abstain in zip(should_abstain, abstained)
    )
    n5 = sum(
        required and did_abstain
        for required, did_abstain in zip(should_abstain, abstained)
    )
    total = len(should_abstain)
    precision = _safe_divide(n5, n3 + n5)
    recall = _safe_divide(n5, n2 + n4 + n5)
    return {
        "count": total,
        "abstention_precision": precision,
        "abstention_recall": recall,
        "abstention_f1": _safe_divide(2 * precision * recall, precision + recall),
        "abstention_accuracy": _safe_divide(n1 + n5, total),
        "coverage": _safe_divide(n1 + n2 + n4, total),
        "abstention_rate": _safe_divide(n3 + n5, total),
        "effective_reliability": _safe_divide(n1 - n2 - n4, total),
        "outcomes": {
            "N1_correct_answer": n1,
            "N2_incorrect_answer": n2,
            "N3_unneeded_abstention": n3,
            "N4_answer_when_abstention_required": n4,
            "N5_correct_abstention": n5,
        },
        "confusion_matrix": {
            "ground_truth": ["should_answer", "should_abstain"],
            "response": ["correct_answer", "incorrect_answer", "abstained"],
            "counts": [[n1, n2, n3], [0, n4, n5]],
        },
    }


def accuracy(values):
    values = list(values)
    return {
        "count": len(values),
        "correct": sum(values),
        "accuracy": sum(values) / len(values) if values else None,
    }


def flatten(cases):
    return [turn for case in cases for turn in case.get("turns", [case])]


def summarize(cases):
    from .scoring import (
        actual_labels,
        entity_pairs,
        expected_abstention,
        gold_labels,
        query_key,
    )

    rows = flatten(cases)
    annotated = [
        (row, gold_labels(row["expected"]), actual_labels(row["actual"]))
        for row in rows
    ]
    classification = {}
    for field in ("intent", "qtype"):
        pairs = [
            (
                str(gold[field]),
                str(predicted[field]) if predicted[field] is not None else "UNKNOWN",
            )
            for _, gold, predicted in annotated
            if field in gold
        ]
        classification[field] = (
            _intent_metrics([a for a, _ in pairs], [b for _, b in pairs])
            if pairs
            else None
        )
    entity_matches = []
    tp = fp = fn = 0
    slots = {}
    for _, gold, predicted in annotated:
        if "entities" not in gold:
            continue
        truth, guess = gold["entities"], predicted["entities"]
        entity_matches.append(guess in (None, {}) if not truth else guess == truth)
        expected_pairs, actual_pairs = entity_pairs(truth), entity_pairs(guess)
        tp += len(expected_pairs & actual_pairs)
        fp += len(actual_pairs - expected_pairs)
        fn += len(expected_pairs - actual_pairs)
        for slot in {slot for slot, _ in expected_pairs | actual_pairs}:
            counts = slots.setdefault(slot, Counter())
            a = {pair for pair in expected_pairs if pair[0] == slot}
            b = {pair for pair in actual_pairs if pair[0] == slot}
            counts.update(tp=len(a & b), fp=len(b - a), fn=len(a - b))

    def prf(tp, fp, fn):
        return {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        }

    annotations = [expected_abstention(row["expected"]) for row in rows]
    abstention = (
        _abstention_metrics(
            annotations,
            [row["actual_abstained"] for row in rows],
            [row["correct"] for row in rows],
        )
        if all(a is not None for a in annotations)
        else None
    )
    if abstention:
        outcomes = abstention["outcomes"]
        n1, n2, n3, n4, n5 = (
            outcomes[key]
            for key in (
                "N1_correct_answer",
                "N2_incorrect_answer",
                "N3_unneeded_abstention",
                "N4_answer_when_abstention_required",
                "N5_correct_abstention",
            )
        )
        # Preserve the survey convention above and identify standard binary decision metrics separately.
        precision = _safe_divide(n5, n3 + n5)
        recall = _safe_divide(n5, n4 + n5)
        abstention["binary_decision"] = {
            "precision": precision,
            "recall": recall,
            "f1": _safe_divide(2 * precision * recall, precision + recall),
            "accuracy": _safe_divide(n1 + n2 + n5, len(rows)),
            "note": "Decision correctness only; an incorrect non-abstaining answer remains a correct should-answer decision.",
        }
    fields = sorted({key for row in rows for key in row["checks"]})
    attempted = [
        row
        for row in rows
        if row["actual"].get("statistical_attempted")
        or row["actual"].get("statistical_prediction") is not None
    ]
    accepted = [row for row in rows if row["actual"].get("statistical_used")]
    accepted_semantic = []
    for row, gold, predicted in annotated:
        if (
            row["actual"].get("statistical_used")
            and {"intent", "qtype", "entities"} <= gold.keys()
        ):
            accepted_semantic.append(gold == predicted)
    semantic_frames = []
    unknown_requests = []
    for row, gold, predicted in annotated:
        if gold.get("intent") == "UNKNOWN":
            unknown_requests.append(predicted["intent"] not in (None, "UNKNOWN"))
        if not {"intent", "qtype", "entities"} <= gold.keys():
            continue
        frame = row["actual"].get("semantic")
        semantic_frames.append(
            frame is None
            if gold["intent"] == "UNKNOWN"
            else bool(
                frame
                and frame.get("predicate") == gold["intent"]
                and frame.get("qtype") == gold["qtype"]
                and entity_pairs(frame.get("arguments"))
                == entity_pairs(gold["entities"])
            )
        )
    dialogues = [case for case in cases if "turns" in case]
    latencies = sorted(row["elapsed_ms"] for row in rows)
    return {
        "task_performance": {
            "end_to_end_accuracy": _safe_divide(
                sum(case["correct"] for case in cases), len(cases)
            ),
            "turn_accuracy": accuracy(row["correct"] for row in rows),
            "intent_classification": classification["intent"],
            "qtype_classification": classification["qtype"],
            "entity_extraction_exact_match_accuracy": _safe_divide(
                sum(entity_matches), len(entity_matches)
            )
            if entity_matches
            else None,
            "entity_extraction_count": len(entity_matches),
            "entity_extraction_micro": {
                "count": len(entity_matches),
                **prf(tp, fp, fn),
                "per_slot": {
                    slot: prf(c["tp"], c["fp"], c["fn"])
                    for slot, c in sorted(slots.items())
                },
            },
            "semantic_frame_accuracy": accuracy(semantic_frames),
            "query_logical_equivalence": accuracy(
                query_key(row["expected"]["query"])
                == query_key(row["actual"].get("query"))
                for row in rows
                if "query" in row["expected"]
            ),
            "unknown_requests": {
                "count": len(unknown_requests),
                "false_accepts": sum(unknown_requests),
                "false_acceptance_rate": sum(unknown_requests) / len(unknown_requests)
                if unknown_requests
                else None,
            },
            "field_accuracy": {
                field: accuracy(
                    row["checks"][field] for row in rows if field in row["checks"]
                )
                for field in fields
            },
            "parser": {
                "count": len(rows),
                "parsed": sum(
                    row["actual"].get("parse_tree", "()") != "()" for row in rows
                ),
                "note": "Coverage, not syntactic or semantic correctness.",
            },
        },
        "abstention_performance": abstention,
        "abstention_note": None
        if abstention
        else "No abstention labels supplied; annotate every turn to enable these metrics.",
        "fallback_performance": {
            "attempted": len(attempted),
            "accepted": len(accepted),
            "acceptance_rate": len(accepted) / len(attempted) if attempted else None,
            "accepted_case_checks": accuracy(row["correct"] for row in accepted),
            "accepted_semantic_accuracy": accuracy(accepted_semantic),
        },
        "dialogue_performance": {
            "sessions": accuracy(case["correct"] for case in dialogues),
            "reference_checks": accuracy(
                row["checks"]["context_used"]
                for row in rows
                if "context_used" in row["checks"]
            ),
        },
        "groups": {
            tag: accuracy(case["correct"] for case in cases if tag in case["tags"])
            for tag in sorted({tag for case in cases for tag in case["tags"]})
        },
        "group_turns": {
            tag: accuracy(
                row["correct"]
                for case in cases
                if tag in case["tags"]
                for row in flatten([case])
            )
            for tag in sorted({tag for case in cases for tag in case["tags"]})
        },
        "latency_ms": {
            "count": len(rows),
            "median": median(latencies),
            "p95": latencies[ceil(0.95 * len(latencies)) - 1],
            "note": "Sequential wall time per turn; initialization excluded, not a load benchmark.",
        },
    }


def comparison(baseline, primary):
    before = flatten(baseline)
    after = flatten(primary)
    recovered = []
    regressed = []
    for a, b in zip(before, after):
        identity = {"case_id": b["case_id"], "turn": b["turn"], "input": b["input"]}
        if not a["correct"] and b["correct"]:
            recovered.append(identity)
        if a["correct"] and not b["correct"]:
            regressed.append(identity)
    return {
        "evaluated_turns": len(after),
        "fallback_accepted_incorrect_turns": sum(
            bool(row["actual"].get("statistical_used")) and not row["correct"]
            for row in after
        ),
        "recovered_turns": recovered,
        "regressed_turns": regressed,
        "turn_accuracy_delta": (
            sum(row["correct"] for row in after) - sum(row["correct"] for row in before)
        )
        / len(after),
    }
