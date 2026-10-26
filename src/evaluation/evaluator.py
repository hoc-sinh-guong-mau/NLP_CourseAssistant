"""Small smoke evaluation; replace/expand with an independent test set."""
import json

from src.common import run_stage
from src.common.files import read_text, write_text
from src.config import ROOT, OUTPUT_DIR
from src.application.pipeline import CourseAssistant

from .exceptions import EvaluationError


def evaluate(assistant=None, *, cases_path=ROOT / "input/test_cases.jsonl", output_path=OUTPUT_DIR / "evaluation.txt"):
    assistant = CourseAssistant() if assistant is None else assistant
    cases = [run_stage("evaluation", json.loads, line) for line in read_text(cases_path, EvaluationError).splitlines() if line.strip()]
    if not cases:
        raise EvaluationError("Evaluation dataset must not be empty")
    for number, case in enumerate(cases, 1):
        if not isinstance(case, dict) or not isinstance(case.get("input"), str) or not isinstance(case.get("expected"), dict) or not case["expected"]:
            raise EvaluationError("Each evaluation case needs input and nonempty expected fields", context={"case": number})
    results = []
    for case in cases:
        actual = assistant.process(case["input"])
        correct = all(actual.get(key) == value for key, value in case["expected"].items())
        results.append({"input": case["input"], "correct": correct, "actual": actual})
    report = {
        "note": "Smoke checks only; not a representative benchmark or answer accuracy.",
        "backend": "sqlite",
        "total": len(results), "passed": sum(r["correct"] for r in results),
        "cases": results,
    }
    write_text(output_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n", EvaluationError)
    print(f"Smoke checks: {report['passed']}/{report['total']}")
    return report


def main():
    report = evaluate()
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
