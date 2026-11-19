"""One reproducible report artifact with explicit metric and dataset limitations."""
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from src.common.files import write_text
from .exceptions import EvaluationError


def dataset_metadata(path, cases):
    path = Path(path)
    content = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(content).hexdigest(),
            'cases': len(cases), 'turns': sum(len(case['turns']) for case in cases),
            'dialogues': sum(case['dialogue'] for case in cases),
            'note': 'Labels are supplied by the dataset author, never generated from current predictions. '
                    'The bundled authored suite is a development/regression set, not an unseen benchmark.'}


def runtime_metadata(assistant):
    recognizer = getattr(assistant, 'statistical_recognizer', None)
    threshold = getattr(recognizer, 'unknown_threshold', None)
    dependencies = {}
    for name in ('nlp-course-assistant', 'nltk', 'scikit-learn', 'joblib'):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    return {'assistant': type(assistant).__name__,
            'statistical_model_loaded': recognizer is not None,
            'recognizer': type(recognizer).__name__ if recognizer is not None else None,
            'unknown_threshold': threshold if isinstance(threshold, (int, float)) else None,
            'dependencies': dependencies}


def write_report(path, report):
    write_text(path, json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', EvaluationError)
