"""Generate the statistical dataset, train the qtype classifier, and evaluate it."""
import json

from sklearn.metrics import accuracy_score, classification_report

from src.config import DATA_DIR, QTYPE_MODEL_PATH
from src.statistical_processing.dataset import (
    generate_labeled_dataset,
    load_labeled_dataset,
    save_json,
    split_labeled_dataset,
)
from src.statistical_processing.intent_recognizer import (
    QTypeRecognizer,
    build_qtype_to_intent,
)


DATASET_DIR = DATA_DIR / "stat_dataset"
DATASET_PATH = DATASET_DIR / "dataset.json"
MODEL_PATH = QTYPE_MODEL_PATH
MODEL_DIR = MODEL_PATH.parent
SPLIT_SEED = 42


def main():
    save_json(DATASET_PATH, generate_labeled_dataset(sample_count=1000, seed=SPLIT_SEED))
    records = load_labeled_dataset(DATASET_PATH)
    splits = split_labeled_dataset(records, seed=SPLIT_SEED)
    for name, rows in splits.items():
        save_json(DATASET_DIR / f"{name}.json", rows)

    x_train = [record["sentence"] for record in splits["train"]]
    y_train = [record["qtype"] for record in splits["train"]]
    qtype_to_intent = build_qtype_to_intent(
        [record["qtype"] for record in records],
        [record["intent"] for record in records],
    )
    recognizer = QTypeRecognizer(
        sorted(qtype_to_intent),
        qtype_to_intent,
        unknown_threshold=0.05,
    )
    recognizer.train(x_train, y_train)
    recognizer.save_model(MODEL_PATH)

    x_validation = [record["sentence"] for record in splits["validation"]]
    y_validation = [record["qtype"] for record in splits["validation"]]
    raw_validation = recognizer.model.predict(recognizer.vectorizer.transform(x_validation))
    validation_intents = [qtype_to_intent[qtype] for qtype in y_validation]
    predicted_intents = [qtype_to_intent[qtype] for qtype in raw_validation]

    x_test = [record["sentence"] for record in splits["test"]]
    y_test = [record["qtype"] for record in splits["test"]]
    raw_test = recognizer.model.predict(recognizer.vectorizer.transform(x_test))
    test_intents = [qtype_to_intent[qtype] for qtype in y_test]
    predicted_test_intents = [qtype_to_intent[qtype] for qtype in raw_test]
    fallback_predictions = [recognizer.predict_intent(sentence) for sentence in x_test]
    covered = [prediction for prediction in fallback_predictions if prediction[0] != "UNKNOWN"]

    metrics = {
        "dataset_size": len(records),
        "qtype_count": len(qtype_to_intent),
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "validation": {
            "qtype_accuracy": accuracy_score(y_validation, raw_validation),
            "intent_accuracy": accuracy_score(validation_intents, predicted_intents),
        },
        "test": {
            "qtype_accuracy": accuracy_score(y_test, raw_test),
            "intent_accuracy": accuracy_score(test_intents, predicted_test_intents),
            "fallback_coverage": len(covered) / len(fallback_predictions),
            "fallback_accuracy_when_covered": (
                sum(prediction[1] == truth for prediction, truth in zip(fallback_predictions, y_test)
                    if prediction[0] != "UNKNOWN") / len(covered)
                if covered else 0.0
            ),
            "unknown_threshold": recognizer.unknown_threshold,
            "classification_report": classification_report(
                y_test, raw_test, output_dict=True, zero_division=0
            ),
        },
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = MODEL_DIR / "metrics.json"
    with metrics_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)
        file.write("\n")

    loaded = QTypeRecognizer.load_model(MODEL_PATH)
    sample = splits["test"][0]
    prediction = loaded.predict_intent(sample["sentence"])
    if prediction[1] != sample["qtype"]:
        raise RuntimeError(
            f"Saved model smoke test failed: expected {sample['qtype']}, got {prediction[1]}"
        )

    printable_metrics = {
        **metrics,
        "test": {key: value for key, value in metrics["test"].items()
                 if key != "classification_report"},
    }
    print(json.dumps({
        "model": str(MODEL_PATH),
        "dataset": str(DATASET_PATH),
        "metrics": printable_metrics,
        "save_reload_smoke_test": {
            "sentence": sample["sentence"],
            "expected_intent": sample["intent"],
            "expected_qtype": sample["qtype"],
            "prediction": prediction,
        },
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
