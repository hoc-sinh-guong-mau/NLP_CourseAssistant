"""Evaluate fixed gold cases, isolated dialogues and optional grammar-only ablation."""

import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter

from src.application.pipeline import CourseAssistant
from src.common.files import write_text
from src.config import OUTPUT_DIR, SMOKE_CASES_PATH
from src.dialogue import DialogueSession

from . import metrics
from .dataset import load_evaluation_data
from .exceptions import EvaluationError
from .reporting import answer_performance, describe_failures

# Existing private helpers remain importable for callers/tests of earlier reports.
from .scoring import expected_abstention, score

_expected_abstention = expected_abstention
_intent_metrics = metrics._intent_metrics
_abstention_metrics = metrics._abstention_metrics


def _run(cases, assistant):
    results = []
    for case in cases:
        process = (
            DialogueSession(assistant).process
            if case["dialogue"]
            else assistant.process
        )
        turns = []
        for number, turn in enumerate(case["turns"], 1):
            started = perf_counter()
            actual = process(turn["input"])
            elapsed_ms = (perf_counter() - started) * 1000
            turns.append(
                {
                    "case_id": case["id"],
                    "turn": number,
                    "input": turn["input"],
                    "elapsed_ms": elapsed_ms,
                    **score(turn["expected"], actual),
                }
            )
        common = {"id": case["id"], "tags": case["tags"]}
        if case["dialogue"]:
            results.append(
                {
                    **common,
                    "correct": all(row["correct"] for row in turns),
                    "turns": turns,
                }
            )
        else:
            results.append({**common, **turns[0]})
    return {
        "total": len(results),
        "passed": sum(case["correct"] for case in results),
        **metrics.summarize(results),
        "answer_performance": answer_performance(results),
        "cases": results,
    }


def _runtime(assistant):
    recognizer = getattr(assistant, "statistical_recognizer", None)
    threshold = getattr(recognizer, "unknown_threshold", None)
    model_path = getattr(recognizer, "model_path", None)
    model = None
    if isinstance(model_path, (str, Path)):
        try:
            model = {
                "path": str(model_path),
                "sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
            }
        except OSError as exc:
            raise EvaluationError(
                "Cannot fingerprint loaded model", context={"path": str(model_path)}
            ) from exc
    return {
        "python": platform.python_version(),
        "statistical_model_loaded": recognizer is not None,
        "recognizer": type(recognizer).__name__ if recognizer is not None else None,
        "unknown_threshold": threshold if isinstance(threshold, (float, int)) else None,
        "model": model,
    }


def evaluate(
    assistant=None,
    *,
    cases_path=SMOKE_CASES_PATH,
    output_path=OUTPUT_DIR / "evaluation.txt",
    compare=False,
    baseline=None,
    dialogue_cases_path=None,
):
    if Path(cases_path).resolve() == Path(output_path).resolve():
        raise EvaluationError("Evaluation input and output must be different files")
    if baseline is not None and not compare:
        raise EvaluationError("An explicit baseline requires compare=True")
    if (
        dialogue_cases_path is not None
        and Path(dialogue_cases_path).resolve() == Path(output_path).resolve()
    ):
        raise EvaluationError(
            "Dialogue labels and evaluation output must be different files"
        )
    cases, metadata = load_evaluation_data(cases_path, dialogue_cases_path)
    assistant = CourseAssistant() if assistant is None else assistant
    baseline_report = None
    if compare:
        if baseline is None:
            baseline = CourseAssistant(
                parser=assistant.parser,
                semantic=assistant.semantic,
                kb=assistant.kb,
                query_builder=assistant.query_builder,
                answer_generator=assistant.answer_generator,
                use_statistical=False,
            )
        baseline_report = {**_run(cases, baseline), "runtime": _runtime(baseline)}
    report = {
        "schema_version": 3,
        "backend": "sqlite",
        "dataset": str(cases_path),
        "dataset_metadata": metadata,
        "note": "Exact checks preserve supplied gold. Component metrics exclude contradictory fields. "
        "Dataset overlap and label quality must be reviewed before claiming generalization.",
        **_run(cases, assistant),
        "runtime": _runtime(assistant),
    }
    if compare:
        report["comparison"] = {
            **metrics.comparison(baseline_report["cases"], report["cases"]),
            "grammar_only": baseline_report,
        }
        if not report["runtime"]["statistical_model_loaded"]:
            report["comparison"]["warning"] = (
                "No statistical model loaded; primary cannot use fallback."
            )
    systems = {"primary": report}
    if baseline_report is not None:
        systems["grammar_only"] = baseline_report
    report["failures"], report["error_analysis"] = describe_failures(systems, metadata)
    report["method_notes"] = {
        "strengths": [
            "Traceable parse/semantic/query pipeline and grounded KB answers.",
            "Fixed gold, model fingerprint and grammar-only ablation support reproducibility.",
        ],
        "limitations": [
            "A finite development set and grammar-generated training data do not establish generalization.",
            "Conflicting annotations and exact wording can distort raw case accuracy; inspect the audit.",
            "Lexicon matching and local reference rules cover only a bounded domain.",
            "Answer metrics are annotation checks, not an automatic factuality judge.",
        ],
    }
    write_text(
        output_path,
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        EvaluationError,
    )
    print(
        f"End-to-end accuracy: {report['passed']}/{report['total']}; report: {output_path}"
    )
    return report


def main():
    report = evaluate()
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
