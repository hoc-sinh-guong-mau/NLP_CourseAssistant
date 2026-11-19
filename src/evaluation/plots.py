"""Render an existing evaluation report without running the NLP pipeline."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

from src.common.files import read_text

from .exceptions import EvaluationError


@dataclass(frozen=True)
class _Chart:
    filename: str
    title: str
    labels: list
    values: list
    rows: list | None = None


def _score(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Metric must be a number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Metric must be finite and between 0 and 1")
    return value


def _matrix(filename, title, columns, rows, values):
    for labels in (columns, rows):
        if not isinstance(labels, list) or not 1 <= len(labels) <= 120:
            raise ValueError("Confusion matrix must have 1 to 120 labels")
        if not all(isinstance(label, str) and label for label in labels):
            raise ValueError("Confusion matrix labels must be nonempty strings")
        if len(set(labels)) != len(labels):
            raise ValueError("Confusion matrix labels must be unique")
    if not isinstance(values, list) or len(values) != len(rows):
        raise ValueError("Confusion matrix row count does not match labels")
    for row in values:
        if not isinstance(row, list) or len(row) != len(columns):
            raise ValueError("Confusion matrix column count does not match labels")
        if any(type(value) is not int or value < 0 for value in row):
            raise ValueError("Confusion matrix counts must be nonnegative integers")
    return _Chart(filename, title, columns, values, rows)


def _charts(report):
    """Validate all consumed fields before creating any files."""
    if not isinstance(report, dict) or report.get("schema_version") != 3:
        raise ValueError("Expected an evaluation report with schema_version=3")
    systems = [("Primary", report)]
    baseline = report.get("comparison", {}).get("grammar_only")
    if baseline:
        systems.append(("Grammar only", baseline))
    charts = []
    for name, system in systems:
        task = system["task_performance"]
        labels, scores = (
            ["Case accuracy", "Turn accuracy"],
            [
                _score(task["end_to_end_accuracy"]),
                _score(task["turn_accuracy"]["accuracy"]),
            ],
        )
        for field, label in [
            ("intent_classification", "Intent macro F1"),
            ("qtype_classification", "Qtype macro F1"),
            ("entity_extraction_micro", "Entity micro F1"),
        ]:
            metric = task.get(field)
            if metric and metric.get("count", 0) and metric.get("f1") is not None:
                labels.append(label)
                scores.append(_score(metric.get("macro_f1", metric["f1"])))
        charts.append(
            _Chart(
                "summary.png" if name == "Primary" else "grammar_only_summary.png",
                f"{name}: annotated task metrics",
                labels,
                scores,
            )
        )
    task = report["task_performance"]
    for kind in ("intent", "qtype"):
        metric = task.get(f"{kind}_classification")
        if not metric or not metric.get("count", 0):
            continue
        cm = metric["confusion_matrix"]
        labels, counts = cm["labels"], cm["counts"]
        charts.append(
            _matrix(
                f"{kind}_confusion_matrix.png",
                f"Primary {kind}: counts (n={metric['count']})",
                labels,
                labels,
                [[counts[a][b] for b in labels] for a in labels],
            )
        )
    abstention = report.get("abstention_performance")
    if abstention and abstention.get("count", 0):
        cm = abstention["confusion_matrix"]
        charts.append(
            _matrix(
                "abstention_confusion_matrix.png",
                "Primary abstention: task-aware counts",
                cm["response"],
                cm["ground_truth"],
                cm["counts"],
            )
        )
    errors = report.get("error_analysis", {}).get("primary", {}).get("counts", {})
    if errors:
        if not isinstance(errors, dict) or len(errors) > 120:
            raise ValueError("Invalid error categories")
        if any(
            not isinstance(k, str) or type(v) is not int or v < 0
            for k, v in errors.items()
        ):
            raise ValueError("Invalid error category counts")
        labels = sorted(errors, key=lambda k: (-errors[k], k))
        charts.append(
            _Chart(
                "error_categories.png",
                "Primary failures: observed categories (turns)",
                labels,
                [errors[k] for k in labels],
            )
        )
    return charts


def plot_evaluation(input_path, output_dir):
    """Return generated PNG paths. Never retrain a model or modify the report."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    try:
        report = json.loads(
            read_text(input_path, EvaluationError, encoding="utf-8-sig")
        )
        charts = _charts(report)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        if isinstance(exc, EvaluationError):
            raise
        raise EvaluationError(
            f"Invalid evaluation report {input_path}: {exc}",
            context={"path": str(input_path)},
        ) from exc
    paths = [output_dir / chart.filename for chart in charts]
    if input_path.resolve() in [path.resolve() for path in paths]:
        raise EvaluationError("Chart output must not overwrite the input report")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for chart, path in zip(charts, paths):
            size = max(8, min(26, len(chart.labels) * 0.34))
            fig, ax = plt.subplots(figsize=(size, size if chart.rows else 5))
            try:
                if chart.rows is not None:
                    image = ax.imshow(chart.values, cmap="Blues", aspect="auto")
                    fig.colorbar(image, ax=ax, label="Count")
                    ax.set_xticks(range(len(chart.labels)), chart.labels, rotation=90)
                    ax.set_yticks(range(len(chart.rows)), chart.rows)
                    ax.set_xlabel("Predicted / response")
                    ax.set_ylabel("Gold")
                    if len(chart.labels) <= 15:
                        for i, row in enumerate(chart.values):
                            for j, value in enumerate(row):
                                ax.text(
                                    j,
                                    i,
                                    str(value),
                                    ha="center",
                                    va="center",
                                    color="white"
                                    if value > image.get_clim()[1] / 2
                                    else "black",
                                )
                else:
                    bars = ax.barh(chart.labels, chart.values, color="#2563eb")
                    ax.invert_yaxis()
                    is_score = "summary" in chart.filename
                    if is_score:
                        ax.set_xlim(0, 1.15)
                    ax.set_xlabel(
                        "Score (0–1)" if is_score else "Number of failed turns"
                    )
                    ax.bar_label(bars, fmt="%.3f" if is_score else "%.0f", padding=4)
                ax.set_title(chart.title)
                fig.tight_layout()
                fig.savefig(path, dpi=140, bbox_inches="tight")
            finally:
                plt.close(fig)
    except OSError as exc:
        raise EvaluationError(
            f"Cannot write charts to {output_dir}", context={"path": str(output_dir)}
        ) from exc
    return paths
