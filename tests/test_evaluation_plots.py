"""Real rendering and CLI checks without a database or trained model."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.config import ROOT
from src.evaluation.exceptions import EvaluationError
from src.evaluation.metrics import _intent_metrics
from src.evaluation.plots import plot_evaluation


def report():
    return {
        "schema_version": 3,
        "task_performance": {
            "end_to_end_accuracy": 0.5,
            "turn_accuracy": {"count": 2, "correct": 1, "accuracy": 0.5},
            "intent_classification": _intent_metrics(["A", "B"], ["A", "A"]),
            "qtype_classification": None,
        },
    }


class EvaluationPlotTests(unittest.TestCase):
    def test_minimal_report_renders_only_available_metrics_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "evaluation.txt"
            source.write_text(json.dumps(report()))
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            paths = plot_evaluation(source, root / "charts")
            self.assertEqual(
                {p.name for p in paths}, {"summary.png", "intent_confusion_matrix.png"}
            )
            for path in paths:
                self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_comparison_abstention_and_error_charts(self):
        data = report()
        data["comparison"] = {"grammar_only": copy.deepcopy(data)}
        data["abstention_performance"] = {
            "count": 2,
            "confusion_matrix": {
                "ground_truth": ["should_answer", "should_abstain"],
                "response": ["correct", "incorrect", "abstained"],
                "counts": [[1, 0, 0], [0, 0, 1]],
            },
        }
        data["error_analysis"] = {"primary": {"counts": {"missing_evidence": 1}}}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "evaluation.txt"
            source.write_text(json.dumps(data))
            paths = plot_evaluation(source, Path(directory) / "charts")
            self.assertEqual(len(paths), 5)

    def test_invalid_reports_fail_before_creating_output(self):
        bad_matrix = report()
        bad_matrix["task_performance"]["intent_classification"]["confusion_matrix"][
            "counts"
        ]["A"]["A"] = -1
        bad_score = report()
        bad_score["task_performance"]["end_to_end_accuracy"] = float("nan")
        for data in (
            "broken JSON",
            "{}",
            json.dumps(bad_matrix),
            json.dumps(bad_score),
        ):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                source, output = (
                    Path(directory) / "report.txt",
                    Path(directory) / "charts",
                )
                source.write_text(data)
                with self.assertRaises(EvaluationError):
                    plot_evaluation(source, output)
                self.assertFalse(output.exists())

    def test_missing_report_is_evaluation_error(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(EvaluationError),
        ):
            plot_evaluation(Path(directory) / "missing", Path(directory) / "charts")

    def test_cli_plot_does_not_initialize_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "report.txt", Path(directory) / "charts"
            source.write_text(json.dumps(report()))
            env = {
                **os.environ,
                "COURSE_DATABASE": str(Path(directory) / "missing.sqlite3"),
                "COURSE_QTYPE_MODEL": str(Path(directory) / "missing.joblib"),
            }
            code = """
import sys
sys.modules['src.application.runner'] = None
from src.main import main
main()
"""
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    code,
                    "plot",
                    "--input",
                    str(source),
                    "--output-dir",
                    str(output),
                ],
                check=False,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Generated 2 charts", result.stdout)
            self.assertFalse((Path(directory) / "missing.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
