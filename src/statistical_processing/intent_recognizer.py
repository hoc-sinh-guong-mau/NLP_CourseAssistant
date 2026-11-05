import re
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # no display needed; we only save figures
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)

UNKNOWN = "UNKNOWN"

# ---------------------------------------------------------------------
# Patterns. ADJUST THESE if your files look different.
# ---------------------------------------------------------------------
# Grammar: matches feature annotations like  [QTYPE = DEADLINE]  or  QTYPE='DEADLINE'
GRAMMAR_QTYPE_RE = re.compile(r"QTYPE\s*=\s*['\"]?([A-Za-z][A-Za-z0-9_]*)")

# Training target line, e.g.  "-> GET_ASSIGNMENT(assignment_id=BTL01): qtype=DEADLINE"
TARGET_INTENT_RE = re.compile(r"->\s*([A-Z_]+)")
TARGET_QTYPE_RE = re.compile(r"(?:qtype|QTYPE)\s*[=:]\s*['\"]?([A-Za-z][A-Za-z0-9_]*)")


# =====================================================================
# Grammar -> available qtypes
# =====================================================================

def load_qtypes_from_grammar(path, patterns=("*.fcfg", "*.cfg", "*.grammar", "*.txt")):
    """
    Collect every distinct QTYPE value that appears in the grammar.

    path : a grammar file, or a directory containing grammar files.
    Returns a sorted list of qtype strings (UNKNOWN is never included).
    """
    path = Path(path)

    if path.is_dir():
        files = sorted({f for p in patterns for f in path.rglob(p)})
    elif path.is_file():
        files = [path]
    else:
        raise FileNotFoundError(f"Grammar path not found: {path}")

    qtypes = set()
    for file in files:
        text = file.read_text(encoding="utf-8")
        # drop comment lines so commented-out rules don't count
        text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        qtypes.update(GRAMMAR_QTYPE_RE.findall(text))

    qtypes.discard(UNKNOWN)

    if not qtypes:
        raise ValueError(
            f"No QTYPE values found in {path}. Check GRAMMAR_QTYPE_RE matches your grammar syntax."
        )
    return sorted(qtypes)


# =====================================================================
# Data
# =====================================================================

def build_data(folderpath):
    """
    Read *.txt files: a sentence line followed by a '->' target line.

    Returns
    -------
    X        : list[str]   sentences
    y_qtype  : list[str]   qtype label per sentence
    y_intent : list[str]   intent per sentence (used only to derive qtype->intent)
    """
    X, y_qtype, y_intent = [], [], []

    for filepath in sorted(Path(folderpath).glob("*.txt")):
        with filepath.open("r", encoding="utf-8") as f:
            sentence = None

            for line in f:
                line = line.rstrip("\n\r")
                if not line.strip():
                    continue

                if line.startswith("->"):
                    intent = TARGET_INTENT_RE.match(line)
                    qtype = TARGET_QTYPE_RE.search(line)

                    if intent is None or qtype is None or sentence is None:
                        raise ValueError(
                            f"{filepath.name}: cannot parse intent/qtype/sentence at: {line}"
                        )

                    X.append(sentence)
                    y_intent.append(intent.group(1))
                    y_qtype.append(qtype.group(1))
                    sentence = None
                else:
                    sentence = line[1:] if line.startswith(" ") else line

    return X, y_qtype, y_intent


def build_qtype_to_intent(y_qtype, y_intent):
    """
    Derive qtype -> intent from labelled data and enforce one intent per qtype.
    """
    mapping = {}
    for q, i in zip(y_qtype, y_intent):
        if mapping.setdefault(q, i) != i:
            raise ValueError(
                f"qtype '{q}' maps to both '{mapping[q]}' and '{i}'. "
                "Rename one of them so each qtype has exactly one intent."
            )
    return mapping


# =====================================================================
# Recognizer
# =====================================================================

class QTypeRecognizer:
    """
    TF-IDF + Logistic Regression qtype classifier.

    The label set comes from the grammar (`qtypes`). UNKNOWN is not a learned
    class; it is returned when confidence < `unknown_threshold`.
    The intent is derived from the qtype via `qtype_to_intent`.
    """

    def __init__(
        self,
        qtypes,
        qtype_to_intent=None,
        model=None,
        vectorizer=None,
        unknown_threshold=0.40,
    ):
        if not qtypes:
            raise ValueError("qtypes must be a non-empty collection.")

        self.qtypes = sorted(set(qtypes))
        self.qtype_to_intent = dict(qtype_to_intent or {})
        self.unknown_threshold = unknown_threshold

        self.vectorizer = vectorizer or TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), sublinear_tf=True
        )
        self.model = model or LogisticRegression(max_iter=1000, class_weight="balanced")
        self.is_fitted = False

    # ------------------------------------------------------------ train
    def train(self, X, y):
        if len(X) != len(y):
            raise ValueError("X and y must contain the same number of samples.")

        y = list(y)

        if UNKNOWN in y:
            raise ValueError("UNKNOWN must not be included in training labels.")

        not_in_grammar = sorted(set(y) - set(self.qtypes))
        if not_in_grammar:
            raise ValueError(f"Training labels not defined in the grammar: {not_in_grammar}")

        missing = sorted(set(self.qtypes) - set(y))
        if missing:
            print(f"WARNING: {len(missing)} grammar qtypes have no training examples: {missing}")

        self.model.fit(self.vectorizer.fit_transform(X), y)
        self.is_fitted = True
        return self

    # ------------------------------------------------------------- eval
    def eval(self, X, y, eval_path=None):
        self._check_fitted()

        if len(X) != len(y):
            raise ValueError("X and y must contain the same number of samples.")
        if UNKNOWN in y:
            raise ValueError("UNKNOWN should not be included in evaluation labels.")

        y_true = list(y)
        y_pred = self.model.predict(self.vectorizer.transform(X))

        # Only classes that appear in truth, predictions, or training: keeps report readable.
        labels = sorted(set(y_true) | set(y_pred) | set(self.model.classes_))

        accuracy = accuracy_score(y_true, y_pred)
        report = classification_report(
            y_true, y_pred, labels=labels, target_names=labels, zero_division=0
        )
        cm = confusion_matrix(y_true, y_pred, labels=labels)

        # Intent accuracy comes for free when a mapping is available.
        intent_accuracy = None
        if self.qtype_to_intent:
            t = [self.qtype_to_intent.get(q) for q in y_true]
            p = [self.qtype_to_intent.get(q) for q in y_pred]
            intent_accuracy = accuracy_score(t, p)

        print(f"QType accuracy: {accuracy:.4f}")
        if intent_accuracy is not None:
            print(f"Derived intent accuracy: {intent_accuracy:.4f}")
        print("\nClassification Report:")
        print(report)

        if eval_path is not None:
            eval_path = Path(eval_path)
            eval_path.mkdir(parents=True, exist_ok=True)

            with open(eval_path / "classification_report.txt", "w", encoding="utf-8") as f:
                f.write(f"QType accuracy: {accuracy:.4f}\n")
                if intent_accuracy is not None:
                    f.write(f"Derived intent accuracy: {intent_accuracy:.4f}\n")
                f.write("\nClassification Report:\n")
                f.write(report)

            size = max(12, len(labels) * 0.35)
            fig, ax = plt.subplots(figsize=(size, size * 0.85))
            ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels).plot(
                ax=ax, xticks_rotation=90, colorbar=False
            )
            ax.set_title("QType Classification Confusion Matrix")
            plt.tight_layout()
            fig.savefig(eval_path / "confusion_matrix.png", dpi=200, bbox_inches="tight")
            plt.close(fig)

            print(f"Evaluation results saved to: {eval_path}")

        return {
            "accuracy": accuracy,
            "intent_accuracy": intent_accuracy,
            "classification_report": report,
            "confusion_matrix": cm,
        }

    # ---------------------------------------------------------- predict
    def predict(self, sentence):
        return self.predict_with_confidence(sentence)[0]

    def predict_with_confidence(self, sentence):
        """Returns (qtype | UNKNOWN, confidence)."""
        self._check_fitted()

        if not isinstance(sentence, str):
            raise TypeError("sentence must be a string.")
        if not sentence.strip():
            return UNKNOWN, 0.0

        probs = self.model.predict_proba(self.vectorizer.transform([sentence]))[0]
        best = int(probs.argmax())
        confidence = float(probs[best])

        if confidence < self.unknown_threshold:
            return UNKNOWN, confidence

        return str(self.model.classes_[best]), confidence

    def predict_top_k(self, sentence, k=3):
        """Top-k (qtype, probability) pairs; handy for fallback to the rule-based parser."""
        self._check_fitted()
        probs = self.model.predict_proba(self.vectorizer.transform([sentence]))[0]
        order = probs.argsort()[::-1][:k]
        return [(str(self.model.classes_[i]), float(probs[i])) for i in order]

    def predict_intent(self, sentence):
        """Returns (intent | UNKNOWN, qtype | UNKNOWN, confidence)."""
        qtype, confidence = self.predict_with_confidence(sentence)
        if qtype == UNKNOWN:
            return UNKNOWN, UNKNOWN, confidence
        return self.qtype_to_intent.get(qtype, UNKNOWN), qtype, confidence

    # ------------------------------------------------------ save / load
    def save_model(self, model_path):
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted model.")

        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(
            {
                "vectorizer": self.vectorizer,
                "model": self.model,
                "qtypes": self.qtypes,
                "qtype_to_intent": self.qtype_to_intent,
                "unknown_threshold": self.unknown_threshold,
            },
            model_path,
        )

    @classmethod
    def load_model(cls, model_path):
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        data = joblib.load(model_path)
        obj = cls(
            qtypes=data["qtypes"],
            qtype_to_intent=data.get("qtype_to_intent"),
            model=data["model"],
            vectorizer=data["vectorizer"],
            unknown_threshold=data.get("unknown_threshold", 0.40),
        )
        obj.is_fitted = True
        return obj

    # --------------------------------------------------------- internal
    def _check_fitted(self):
        if not self.is_fitted:
            raise RuntimeError("QTypeRecognizer has not been trained or loaded.")


# =====================================================================
# Example usage
# =====================================================================
if __name__ == "__main__":
    qtypes = load_qtypes_from_grammar("path/to/grammar")      # <- your grammar file or folder
    X, y_qtype, y_intent = build_data("path/to/train")
    qtype_to_intent = build_qtype_to_intent(y_qtype, y_intent)

    rec = QTypeRecognizer(qtypes, qtype_to_intent)
    rec.train(X, y_qtype)

    Xt, yt, _ = build_data("path/to/test")
    rec.eval(Xt, yt, eval_path="eval_out")

    rec.save_model("models/qtype.joblib")
    print(rec.predict_intent("Hạn nộp BTL01 là khi nào?"))
