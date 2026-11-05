from enum import Enum
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ( accuracy_score,
                              classification_report,
                              confusion_matrix,
                              ConfusionMatrixDisplay )

def build_data(folderpath):
    X = []
    y = []

    for filepath in Path(folderpath).glob("*.txt"):
        with filepath.open("r", encoding="utf-8") as f:
            sentence = None

            for line in f:
                line = line.rstrip("\n\r")

                if not line.strip():
                    continue

                if line.startswith("->"):
                    intent = re.match(r"->\s*([A-Z_]+)", line)

                    if intent is None:
                        raise ValueError(f"Invalid target: {line}")

                    X.append(sentence)
                    y.append(intent.group(1))
                    sentence = None
                else:
                    sentence = line[1:] if line.startswith(" ") else line

    return X, y

class Intent(Enum):
    GET_COURSE_INFO = "GET_COURSE_INFO"
    GET_SCHEDULE = "GET_SCHEDULE"
    GET_TOPIC = "GET_TOPIC"
    GET_ASSIGNMENT = "GET_ASSIGNMENT"
    GET_DEADLINE = "GET_DEADLINE"
    GET_RESOURCE = "GET_RESOURCE"
    GET_RULE = "GET_RULE"
    GET_INSTRUCTOR = "GET_INSTRUCTOR"
    GET_LO = "GET_LO"
    UNKNOWN = "UNKNOWN"

class IntentRecognizer:
    """
    Statistical / machine-learning based intent recognition.

    The classifier learns the nine known intents. UNKNOWN is not
    a learned class. It is returned when the classifier confidence
    is below `unknown_threshold`.

    Default model:
        TF-IDF + Logistic Regression
    """

    # UNKNOWN is deliberately excluded.
    TRAINED_INTENTS = [
        Intent.GET_COURSE_INFO,
        Intent.GET_SCHEDULE,
        Intent.GET_TOPIC,
        Intent.GET_ASSIGNMENT,
        Intent.GET_DEADLINE,
        Intent.GET_RESOURCE,
        Intent.GET_RULE,
        Intent.GET_INSTRUCTOR,
        Intent.GET_LO,
    ]

    def __init__(
        self,
        model=None,
        vectorizer=None,
        unknown_threshold=0.40,
    ):
        """
        Parameters
        ----------
        model:
            Any sklearn classifier supporting fit(), predict(),
            and predict_proba().

        vectorizer:
            Any sklearn text vectorizer supporting fit_transform()
            and transform().

        unknown_threshold:
            Minimum confidence required to accept a prediction.
            Otherwise Intent.UNKNOWN is returned.
        """

        self.unknown_threshold = unknown_threshold

        self.vectorizer = vectorizer or TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )

        self.model = model or LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        )

        self.is_fitted = False

    # =========================================================
    # Training
    # =========================================================

    def train(self, X, y):
        """
        Train the intent classifier.

        Parameters
        ----------
        X : list[str]
            Training sentences.

        y : list[Intent | str]
            Corresponding intents.

        Returns
        -------
        IntentRecognition
            The trained instance.
        """

        if len(X) != len(y):
            raise ValueError(
                "X and y must contain the same number of samples."
            )

        y = self._normalize_labels(y)

        # Prevent UNKNOWN from accidentally becoming a learned class.
        for label in y:
            if label == Intent.UNKNOWN.value:
                raise ValueError(
                    "UNKNOWN must not be included in training labels."
                )

        X_features = self.vectorizer.fit_transform(X)

        self.model.fit(X_features, y)

        self.is_fitted = True

        return self

    # =========================================================
    # Evaluation
    # =========================================================

    def eval(self, X, y, eval_path=None):
        """
        Evaluate the intent classifier.

        Parameters
        ----------
        X : list[str]
        Evaluation sentences.

        y : list[Intent | str]
        True intents.

        eval_path : str | Path | None
        Directory where evaluation results will be saved.
        If None, results are only returned and printed.

        Returns
        -------
        dict
        Evaluation statistics.
        """
        self._check_fitted()

        if len(X) != len(y):
            raise ValueError( "X and y must contain the same number of samples.")

        # Normalize true labels
        y_true = self._normalize_labels(y)

        # UNKNOWN should not be part of normal classifier evaluation.
        for label in y_true:
            if label == Intent.UNKNOWN.value:
                raise ValueError("UNKNOWN should not be included in evaluation labels.")

            # Transform input and predict
            X_features = self.vectorizer.transform(X)
            y_pred = self.model.predict(X_features)

            # Only evaluate intents that the model actually learned.
            labels = [ intent.value for intent in self.TRAINED_INTENTS ]

            # Calculate evaluation metrics
            accuracy = accuracy_score(y_true, y_pred)

            report = classification_report(y_true, y_pred, labels=labels,
                                           target_names=labels, zero_division=0 )

            cm = confusion_matrix( y_true, y_pred, labels=labels )

            # Print results
            print(f"Accuracy: {accuracy:.4f}")
            print()
            print("Classification Report:")
            print(report)

            # Save evaluation results
            if eval_path is not None:
                eval_path = Path(eval_path)
                eval_path.mkdir( parents=True, exist_ok=True)

                # Save classification report
                report_path = eval_path / "classification_report.txt"
                
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write( f"Accuracy: {accuracy:.4f}\n\n" )

                    f.write( "Classification Report:\n")
                    f.write(report)

                # Create and save confusion matrix
                fig, ax = plt.subplots(figsize=(12, 10))

                display = ConfusionMatrixDisplay(confusion_matrix=cm,
                                                 display_labels=labels)

                display.plot(ax=ax, xticks_rotation=45)

                ax.set_title("Intent Classification Confusion Matrix")
                
                plt.tight_layout()
                
                confusion_matrix_path = ( eval_path / "confusion_matrix.png")
                
                fig.savefig(confusion_matrix_path, dpi=300,bbox_inches="tight" )
                
            # Close figure so it is not displayed or kept in memory.
            plt.close(fig)
                
            print(f"Evaluation results saved to: {eval_path}")
                
            return { "accuracy": accuracy,
                    "classification_report": report,
                    "confusion_matrix": cm }

    # =========================================================
    # Prediction
    # =========================================================

    def predict(self, sentence):
        """
        Predict the intent of a sentence.

        Parameters
        ----------
        sentence : str
            Input sentence.

        Returns
        -------
        Intent
            Predicted intent or Intent.UNKNOWN.
        """

        intent, _ = self.predict_with_confidence(sentence)

        return intent

    # =========================================================
    # Prediction with confidence
    # =========================================================

    def predict_with_confidence(self, sentence):
        """
        Predict intent and return its confidence.

        Parameters
        ----------
        sentence : str

        Returns
        -------
        tuple[Intent, float]
            (predicted_intent, confidence)
        """

        self._check_fitted()

        if not isinstance(sentence, str):
            raise TypeError(
                "sentence must be a string."
            )

        if not sentence.strip():
            return Intent.UNKNOWN, 0.0

        X = self.vectorizer.transform([sentence])

        probabilities = self.model.predict_proba(X)[0]

        best_index = probabilities.argmax()
        confidence = float(probabilities[best_index])

        if confidence < self.unknown_threshold:
            return Intent.UNKNOWN, confidence

        predicted_label = self.model.classes_[best_index]

        return Intent(predicted_label), confidence

    # =========================================================
    # Save model
    # =========================================================

    def save_model(self, model_path):
        """
        Save the trained model and vectorizer.

        Parameters
        ----------
        model_path : str | Path
            Path to the model file.
        """

        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted model.")

        model_path = Path(model_path)

        model_path.parent.mkdir(parents=True, exist_ok=True)

        data = { "vectorizer": self.vectorizer,
                 "model": self.model,
                 "unknown_threshold": self.unknown_threshold }

        joblib.dump(data, model_path)

    # =========================================================
    # Load model
    # =========================================================

    def load_model(self, model_path):
        """
        Load a previously trained model.

        Parameters
        ----------
        model_path : str | Path
            Path to the saved model.

        Returns
        -------
        IntentRecognition
            The loaded instance.
        """

        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        data = joblib.load(model_path)

        self.vectorizer = data["vectorizer"]
        self.model = data["model"]

        self.unknown_threshold = data.get(
            "unknown_threshold",
            0.40,
        )

        self.is_fitted = True

        return self

    # =========================================================
    # Internal utilities
    # =========================================================

    @staticmethod
    def _normalize_labels(y):
        """
        Convert Intent enum values to strings.

        Example:
            Intent.GET_TOPIC
                ->
            "GET_TOPIC"
        """

        return [ label.value
                 if isinstance(label, Intent)
                 else label
                 for label in y ]

    def _check_fitted(self):
        if not self.is_fitted:
            raise RuntimeError("IntentRecognition has not been trained or loaded.")
