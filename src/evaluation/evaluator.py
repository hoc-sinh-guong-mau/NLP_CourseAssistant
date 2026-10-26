"""Small smoke evaluation; replace/expand with an independent test set."""
import json

from src.common import run_stage
from src.common.files import read_text, write_text
from src.config import ROOT, OUTPUT_DIR
from src.application.pipeline import CourseAssistant

from .exceptions import EvaluationError


def main():
    assistant = CourseAssistant()
    cases = [run_stage("evaluation", json.loads, line) for line in read_text(ROOT / "input" / "test_cases.jsonl", EvaluationError).splitlines() if line.strip()]
    results = []
    for case in cases:
        actual = assistant.process(case["input"])
        correct = all(actual.get(key) == value for key, value in case["expected"].items())
        results.append({"input": case["input"], "correct": correct, "actual": actual})
    report = {
        "note": "Smoke checks only; not a representative benchmark or answer accuracy.",
        "total": len(results), "passed": sum(r["correct"] for r in results),
        "cases": results,
    }
    write_text(OUTPUT_DIR / "evaluation.txt", json.dumps(report, ensure_ascii=False, indent=2) + "\n", EvaluationError)
    print(f"Smoke checks: {report['passed']}/{report['total']}")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
