"""Evaluate end-to-end, intent/entity, and abstention performance."""
import json

from src.common import run_stage
from src.common.files import read_text, write_text
from src.config import INPUT_DIR, OUTPUT_DIR
from src.application.pipeline import CourseAssistant

from .exceptions import EvaluationError


_ABSTENTION_STATUSES = {
    "missing_information", "unsupported_query", # Outside of KB
    "unsupported_semantic", "unsupported_answer", # Outside of Domain

    # Temporily treated as abstention,
    # but unable to parse does not mean 
    # the answer is out of domain
    "parse_failed" 
}


def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _intent_metrics(truth, predictions):
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
        metric: _safe_divide(sum(scores[metric] for scores in per_class.values()), len(labels))
        for metric in ("precision", "recall", "f1")
    }
    return {
        "count": count,
        "accuracy": _safe_divide(sum(a == p for a, p in zip(truth, predictions)), count),
        "precision": _safe_divide(sum(s["precision"] * s["support"] for s in per_class.values()), count),
        "recall": _safe_divide(sum(s["recall"] * s["support"] for s in per_class.values()), count),
        "f1": _safe_divide(sum(s["f1"] * s["support"] for s in per_class.values()), count),
        "macro_f1": macro["f1"],
        "per_class": per_class,
        "confusion_matrix": {"labels": labels, "counts": matrix},
    }


def _abstention_metrics(should_abstain, abstained, task_correct):
    """Compute the survey's five-outcome abstention confusion matrix."""
    n1 = sum(not required and not did_abstain and correct for required, did_abstain, correct in zip(should_abstain, abstained, task_correct))
    n2 = sum(not required and not did_abstain and not correct for required, did_abstain, correct in zip(should_abstain, abstained, task_correct))
    n3 = sum(not required and did_abstain for required, did_abstain in zip(should_abstain, abstained))
    n4 = sum(required and not did_abstain for required, did_abstain in zip(should_abstain, abstained))
    n5 = sum(required and did_abstain for required, did_abstain in zip(should_abstain, abstained))
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
        "outcomes": {"N1_correct_answer": n1, "N2_incorrect_answer": n2,
                     "N3_unneeded_abstention": n3, "N4_answer_when_abstention_required": n4,
                     "N5_correct_abstention": n5},
        "confusion_matrix": {
            "ground_truth": ["should_answer", "should_abstain"],
            "response": ["correct_answer", "incorrect_answer", "abstained"],
            "counts": [[n1, n2, n3], [0, n4, n5]],
        },
    }


def _intent(case, record):
    expected = case["expected"]
    actual = record.get("intent_entity") or {}
    truth = (expected.get("semantic") or {}).get("predicate")
    if truth is None:
        truth = (expected.get("intent_entity") or {}).get("intent")
    prediction = actual.get("intent")
    if prediction is None:
        prediction = (record.get("semantic") or {}).get("predicate")
    return truth, prediction


def _entity_match(case, record):
    expected = case["expected"]
    expected_semantic = expected.get("semantic")
    if expected_semantic is not None and "arguments" in expected_semantic:
        expected_entities = expected_semantic["arguments"]
    elif "intent_entity" in expected and "entities" in expected["intent_entity"]:
        expected_entities = expected["intent_entity"]["entities"]
    else:
        return None
    actual_entities = (record.get("semantic") or {}).get("arguments")
    if actual_entities is None:
        actual_entities = (record.get("intent_entity") or {}).get("entities")
    return actual_entities == expected_entities


def _expected_abstention(expected):
    """Use an explicit label when present, otherwise derive it from expected.status."""
    if "abstain" in expected:
        return expected["abstain"]
    status = expected.get("status")
    return status in _ABSTENTION_STATUSES if isinstance(status, str) else None


def evaluate(assistant=None, *, cases_path=INPUT_DIR / "test_cases.jsonl", output_path=OUTPUT_DIR / "evaluation.txt"):
    assistant = CourseAssistant() if assistant is None else assistant

    cases = [run_stage("evaluation", json.loads, line) for line in read_text(cases_path, EvaluationError).splitlines() if line.strip()]

    if not cases:
        raise EvaluationError("Evaluation dataset must not be empty")
    for number, case in enumerate(cases, 1):
        if not isinstance(case, dict) or not isinstance(case.get("input"), str) or not isinstance(case.get("expected"), dict) or not case["expected"]:
            raise EvaluationError("Each evaluation case needs input and nonempty expected fields", context={"case": number})
        if "abstain" in case["expected"] and not isinstance(case["expected"]["abstain"], bool):
            raise EvaluationError("expected.abstain must be a boolean", context={"case": number})

    results = []
    intent_truth, intent_predictions = [], []
    entity_matches = []
    abstention_truth, abstention_predictions = [], []
    abstention_task_correct = []
    abstention_annotations = [_expected_abstention(case["expected"]) is not None for case in cases]
    if any(abstention_annotations) and not all(abstention_annotations):
        raise EvaluationError("Abstention evaluation needs expected.abstain or a recognized expected.status on every case")

    for case in cases:
        actual = assistant.process(case["input"])
        expected_output = {key: value for key, value in case["expected"].items() if key != "abstain"}
        correct = all(actual.get(key) == value for key, value in expected_output.items())
        results.append({"input": case["input"], "correct": correct, "actual": actual})

        expected_intent, actual_intent = _intent(case, actual)
        if expected_intent is not None:
            intent_truth.append(str(expected_intent))
            intent_predictions.append(str(actual_intent) if actual_intent is not None else "UNRECOGNIZED")
        entity_match = _entity_match(case, actual)
        if entity_match is not None:
            entity_matches.append(entity_match)

        if all(abstention_annotations):
            abstention_truth.append(_expected_abstention(case["expected"]))
            abstention_predictions.append(
                actual.get("abstained") is True
                or actual.get("status") in _ABSTENTION_STATUSES
            )
            abstention_task_correct.append(correct)

    intent = _intent_metrics(intent_truth, intent_predictions) if intent_truth else None
    report = {
        "note": "",
        "backend": "sqlite",
        "total": len(results),
        "passed": sum(r["correct"] for r in results),
        "task_performance": {
            "end_to_end_accuracy": _safe_divide(sum(r["correct"] for r in results), len(results)),
            "intent_classification": intent,
            "entity_extraction_exact_match_accuracy": _safe_divide(sum(entity_matches), len(entity_matches)) if entity_matches else None,
            "entity_extraction_count": len(entity_matches),
        },
        "abstention_performance": _abstention_metrics(abstention_truth, abstention_predictions, abstention_task_correct) if abstention_truth else None,
        "abstention_note": (
            None if abstention_truth else
            "Provide expected.abstain on every case or an expected.status of 'ok' or a recognized abstention status to calculate abstention metrics."
        ),
        "cases": results,
    }

    write_text(output_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n", EvaluationError)

    print(f"End-to-end accuracy: {report['passed']}/{report['total']}")
    return report


def main():
    report = evaluate()
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
