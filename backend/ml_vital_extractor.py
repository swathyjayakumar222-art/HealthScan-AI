"""Supervised ML-assisted extraction of vital-sign lines.

The classifier learns line categories from an authored, synthetic CSV corpus.
It is an educational prototype, not a validated clinical NLP model.
The ML model classifies a line; a constrained parser then reads a number only
from that line and the recognised category to make the result reviewable.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from threading import Lock
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from vital_extractor import FIELDS, PARSE_BOUNDS, extract_vitals

BACKEND_DIR = Path(__file__).resolve().parent
DATASET_PATH = BACKEND_DIR / "data" / "vital_line_dataset.csv"
MODEL_VERSION = "HealthScan ML Vital-Line Classifier v1"
DEFAULT_CONFIDENCE_THRESHOLD = 0.42

_MODEL: Pipeline | None = None
_MODEL_LOCK = Lock()

VALID_LABELS = {
    "heart_rate", "spo2", "blood_pressure",
    "systolic_bp", "diastolic_bp", "temperature", "other",
}

# These parsing patterns are applied only after the ML model assigns a line
# to the corresponding category. They do not classify the line themselves.
VALUE_PATTERNS = {
    "heart_rate": re.compile(
        r"(?:heart\s*[- ]?rate|pulse(?:\s*rate)?|\bhr\b|"
        r"resting\s*pulse|pulse\s*frequency|measured\s*pulse)"
        r"\D{0,35}?(\d{2,3})\b",
        re.I,
    ),
    "spo2": re.compile(
        r"(?:spo\s*2|spo2|oxygen\s*saturation|oxygen\s*sat|"
        r"o2\s*(?:sat|saturation)|blood\s*oxygen\s*saturation|"
        r"pulse\s*oximetry)"
        r"\D{0,35}?(\d{1,3})\s*%?",
        re.I,
    ),
    "blood_pressure": re.compile(
        r"(?:blood\s*pressure|\bbp\b)\D{0,20}?"
        r"(\d{2,3})\s*/\s*(\d{2,3})\b",
        re.I,
    ),
    "systolic_bp": re.compile(
        r"(?:systolic(?:\s*(?:blood\s*pressure|bp))?|\bsbp\b|"
        r"upper\s*blood\s*pressure|sys\s*pressure)"
        r"\D{0,35}?(\d{2,3})\b",
        re.I,
    ),
    "diastolic_bp": re.compile(
        r"(?:diastolic(?:\s*(?:blood\s*pressure|bp))?|\bdbp\b|"
        r"lower\s*blood\s*pressure)"
        r"\D{0,35}?(\d{2,3})\b",
        re.I,
    ),
    "temperature": re.compile(
        r"(?:body\s*temperature|temperature|temp)"
        r"\D{0,35}?(\d{2,3}(?:\.\d+)?)"
        r"\s*°?\s*(Fahrenheit|Celsius|[CF])?\b",
        re.I,
    ),
}


def read_training_rows(path: Path = DATASET_PATH) -> list[tuple[str, str]]:
    """Load the inspectable training examples from CSV."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [
            (row["text"].strip(), row["label"].strip())
            for row in csv.DictReader(handle)
            if row.get("text") and row.get("label")
        ]
    if not rows:
        raise ValueError(f"No labelled training examples were found in {path}.")
    invalid_labels = sorted({label for _, label in rows} - VALID_LABELS)
    if invalid_labels:
        raise ValueError(f"Unknown labels in training data: {invalid_labels}")
    if len({label for _, label in rows}) < len(VALID_LABELS):
        raise ValueError("Training data must contain examples for all seven classes.")
    return rows


def train_classifier(rows: list[tuple[str, str]] | None = None) -> Pipeline:
    """Train the supervised TF-IDF + logistic-regression line classifier."""
    examples = rows if rows is not None else read_training_rows()
    texts = [text for text, _ in examples]
    labels = [label for _, label in examples]

    model = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            lowercase=True,
            strip_accents="unicode",
            sublinear_tf=True,
        )),
        ("classifier", LogisticRegression(
            max_iter=2500,
            class_weight="balanced",
            random_state=42,
        )),
    ])
    model.fit(texts, labels)
    return model


def get_classifier() -> Pipeline:
    """Train once lazily per worker process and reuse the fitted model."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            _MODEL = train_classifier()
    return _MODEL


def _number_for_line(label: str, line: str) -> dict[str, int | float | None]:
    """Extract values only for the class predicted for this line."""
    empty: dict[str, int | float | None] = {field: None for field in FIELDS}

    # Prefer the project's explainable parser where its known patterns match.
    parsed = (extract_vitals(line).get("vitals") or {})
    accepted_fields = {
        "heart_rate": ("heart_rate",),
        "spo2": ("spo2",),
        "blood_pressure": ("systolic_bp", "diastolic_bp"),
        "systolic_bp": ("systolic_bp",),
        "diastolic_bp": ("diastolic_bp",),
        "temperature": ("temperature",),
    }.get(label, ())

    for field in accepted_fields:
        value = parsed.get(field)
        if value is not None:
            empty[field] = value

    # A category-specific fallback makes common alternate phrasing usable
    # without allowing the model to extract arbitrary numbers from other text.
    if label == "blood_pressure" and empty["systolic_bp"] is None and empty["diastolic_bp"] is None:
        match = VALUE_PATTERNS[label].search(line)
        if match:
            empty["systolic_bp"] = int(match.group(1))
            empty["diastolic_bp"] = int(match.group(2))
    elif label in VALUE_PATTERNS and label != "blood_pressure":
        target_field = label
        if empty[target_field] is None:
            match = VALUE_PATTERNS[label].search(line)
            if match:
                if label == "temperature":
                    value = float(match.group(1))
                    unit = (match.group(2) or "").lower()
                    if unit in ("f", "fahrenheit"):
                        value = (value - 32) * 5 / 9
                    value = round(value, 2)
                else:
                    value = int(match.group(1))
                empty[target_field] = value

    # Reject values outside broad format sanity bounds. These are not
    # medical reference ranges and should never be presented as such.
    for field, value in list(empty.items()):
        if value is None:
            continue
        lower, upper = PARSE_BOUNDS[field]
        if not lower <= float(value) <= upper:
            empty[field] = None
    return empty


def extract_vitals_ml(
    text: str,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """Return ML-classified vital values with source snippets and confidence."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Report text must be a non-empty string.")
    if len(text) > 250_000:
        raise ValueError("Report text is too long (maximum 250,000 characters).")
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("Confidence threshold must be between 0 and 1.")

    model = get_classifier()
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    values: dict[str, int | float | None] = {field: None for field in FIELDS}
    evidence: dict[str, dict[str, Any]] = {}
    predictions: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []

    for line_number, line in enumerate(lines, start=1):
        probabilities = model.predict_proba([line])[0]
        classes = list(model.named_steps["classifier"].classes_)
        best_index = max(range(len(probabilities)), key=lambda index: probabilities[index])
        label = str(classes[best_index])
        confidence = float(probabilities[best_index])

        if label == "other":
            continue

        if confidence < confidence_threshold:
            rejected_candidates.append({
                "line_number": line_number,
                "snippet": line[:300],
                "predicted_label": label,
                "confidence": round(confidence, 4),
                "message": "ML confidence was below the configured threshold; this line was not used.",
            })
            continue

        candidates = _number_for_line(label, line)
        found_on_line = [field for field, value in candidates.items() if value is not None]
        predictions.append({
            "line_number": line_number,
            "snippet": line[:300],
            "predicted_label": label,
            "confidence": round(confidence, 4),
            "values_extracted": found_on_line,
        })

        for field in found_on_line:
            if values[field] is None:
                values[field] = candidates[field]
                evidence[field] = {
                    "snippet": line[:300],
                    "line_number": line_number,
                    "predicted_label": label,
                    "confidence": round(confidence, 4),
                    "method": "TF-IDF character n-grams + logistic regression",
                }

    found_count = sum(value is not None for value in values.values())
    quality = {
        "character_count": len(text),
        "nonempty_lines": len(lines),
        "fields_found": found_count,
        "fields_supported": len(FIELDS),
        "coverage_percent": round(found_count / len(FIELDS) * 100, 1),
        "classified_vital_lines": len(predictions),
        "low_confidence_lines_skipped": len(rejected_candidates),
        "mean_predicted_confidence": (
            round(sum(item["confidence"] for item in predictions) / len(predictions), 4)
            if predictions else None
        ),
        "confidence_threshold": confidence_threshold,
        "note": "Confidence describes the line classifier, not correctness or clinical accuracy.",
    }
    return {
        "vitals": values,
        "evidence": evidence,
        "quality": quality,
        "predictions": predictions[:100],
        "rejected_candidates": rejected_candidates[:100],
        "engine": MODEL_VERSION,
        "algorithm": "Character TF-IDF features + supervised logistic regression",
        "training_examples": len(read_training_rows()),
        "training_corpus": "Authored synthetic line-label examples",
        "disclaimer": (
            "Experimental ML extraction. It may misclassify report lines or miss values. "
            "Verify every value against the source document; this is not a diagnostic model."
        ),
    }
