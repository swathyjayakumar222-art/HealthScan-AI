"""Evaluate the trained ML line classifier on a separate authored synthetic holdout.

Run from backend/ with:
    python evaluate_ml_classifier.py

The output measures seven-way line-label classification on this small, synthetic
holdout only. It is not an estimate of performance on real reports or clinical
accuracy. Do not tune the model on these examples and call them an independent
test set afterward.
"""
import csv
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from ml_vital_extractor import get_classifier

HERE = Path(__file__).resolve().parent
EVALUATION_PATH = HERE / "data" / "vital_line_eval.csv"
LABELS = [
    "heart_rate",
    "spo2",
    "blood_pressure",
    "systolic_bp",
    "diastolic_bp",
    "temperature",
    "other",
]


def main():
    with EVALUATION_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        examples = [
            (row["text"].strip(), row["label"].strip())
            for row in csv.DictReader(handle)
            if row.get("text") and row.get("label")
        ]
    if not examples:
        raise SystemExit("No evaluation examples found.")

    texts = [text for text, _ in examples]
    expected = [label for _, label in examples]
    model = get_classifier()
    predicted = model.predict(texts)

    print("Model:", "TF-IDF character n-grams + logistic regression")
    print("Training examples:", sum(1 for _ in open(HERE / "data" / "vital_line_dataset.csv", encoding="utf-8")) - 1)
    print("Synthetic holdout examples:", len(examples))
    print("Line-label accuracy: {:.1f}%".format(100 * accuracy_score(expected, predicted)))
    print("\nClassification report:")
    print(classification_report(expected, predicted, labels=LABELS, zero_division=0, digits=3))
    print("Confusion matrix (rows=true labels, columns=predicted labels):")
    print("Labels:", ", ".join(LABELS))
    print(confusion_matrix(expected, predicted, labels=LABELS))

    mistakes = [
        (text, truth, guess)
        for text, truth, guess in zip(texts, expected, predicted)
        if truth != guess
    ]
    if mistakes:
        print("\nMisclassified holdout examples:")
        for text, truth, guess in mistakes:
            print(f"- {text!r}: expected={truth}, predicted={guess}")
    else:
        print("\nNo misclassified lines in this synthetic holdout.")
    print("\nLimit: these are authored synthetic lines, not real medical-report evaluation.")


if __name__ == "__main__":
    main()
