"""Small smoke evaluation; replace/expand with an independent test set."""
import json
from .config import ROOT, OUTPUT_DIR
from .pipeline import CourseAssistant


def main():
    assistant = CourseAssistant()
    cases = [json.loads(line) for line in (ROOT / "input" / "test_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "evaluation.txt").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Smoke checks: {report['passed']}/{report['total']}")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
