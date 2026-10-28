"""Evaluate vital extraction against a small, synthetic regression corpus.

Run from the backend directory:
    python evaluate_extraction.py

This is a software regression check on authored synthetic examples, not a
clinical validation study and not evidence of performance on real-world PDFs.
"""
from vital_extractor import FIELDS, extract_vitals

DATASET = [
    (
        "Heart Rate: 72 bpm\nSpO2: 98%\nBlood Pressure: 120/80 mmHg\nTemperature: 36.8 C",
        {"heart_rate": 72, "spo2": 98, "systolic_bp": 120, "diastolic_bp": 80, "temperature": 36.8},
    ),
    (
        "Pulse rate: 64 beats/min\nO2 sat: 97%",
        {"heart_rate": 64, "spo2": 97, "systolic_bp": None, "diastolic_bp": None, "temperature": None},
    ),
    (
        "BP - 110/70 mmHg",
        {"heart_rate": None, "spo2": None, "systolic_bp": 110, "diastolic_bp": 70, "temperature": None},
    ),
    (
        "Body temperature: 98.6 F",
        {"heart_rate": None, "spo2": None, "systolic_bp": None, "diastolic_bp": None, "temperature": 37.0},
    ),
    (
        "Systolic: 135 mmHg\nDiastolic: 85 mmHg\nTemp = 37.1 C",
        {"heart_rate": None, "spo2": None, "systolic_bp": 135, "diastolic_bp": 85, "temperature": 37.1},
    ),
    (
        "Patient age 42 years. Lab number 120. Appointment 2026-10-28.",
        {"heart_rate": None, "spo2": None, "systolic_bp": None, "diastolic_bp": None, "temperature": None},
    ),
    (
        "HR 88; oxygen saturation: 95%; BP: 128/82; Temperature: 100.4 F",
        {"heart_rate": 88, "spo2": 95, "systolic_bp": 128, "diastolic_bp": 82, "temperature": 38.0},
    ),
    (
        "No measurements found in this note.",
        {"heart_rate": None, "spo2": None, "systolic_bp": None, "diastolic_bp": None, "temperature": None},
    ),
    (
        "Heart rate=70\nSpO2 99\nBlood pressure 118/76\nBody temperature 37 C",
        {"heart_rate": 70, "spo2": 99, "systolic_bp": 118, "diastolic_bp": 76, "temperature": 37.0},
    ),
]

def main():
    totals = {"tp": 0, "fp": 0, "fn": 0, "exact": 0, "cells": 0}
    per_field = {field: {"tp": 0, "fp": 0, "fn": 0} for field in FIELDS}

    for text, gold in DATASET:
        predicted = extract_vitals(text)["vitals"]
        for field in FIELDS:
            expected, actual = gold[field], predicted[field]
            totals["cells"] += 1
            if expected == actual:
                totals["exact"] += 1
            if expected is not None and actual == expected:
                per_field[field]["tp"] += 1
            else:
                if actual is not None:
                    per_field[field]["fp"] += 1
                if expected is not None:
                    per_field[field]["fn"] += 1

    print(f"Synthetic examples: {len(DATASET)}")
    print("Field-level exact agreement: {:.1f}%".format(100 * totals["exact"] / totals["cells"]))
    print("\nField                 Precision   Recall   F1")
    print("-" * 48)
    micro = {"tp": 0, "fp": 0, "fn": 0}
    for field in FIELDS:
        item = per_field[field]
        precision = item["tp"] / (item["tp"] + item["fp"]) if item["tp"] + item["fp"] else 0.0
        recall = item["tp"] / (item["tp"] + item["fn"]) if item["tp"] + item["fn"] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        micro["tp"] += item["tp"]
        micro["fp"] += item["fp"]
        micro["fn"] += item["fn"]
        print(f"{field:21} {precision:9.3f} {recall:8.3f} {f1:6.3f}")
    p = micro["tp"] / (micro["tp"] + micro["fp"]) if micro["tp"] + micro["fp"] else 0.0
    r = micro["tp"] / (micro["tp"] + micro["fn"]) if micro["tp"] + micro["fn"] else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    print("-" * 48)
    print(f"{'MICRO AVERAGE':21} {p:9.3f} {r:8.3f} {f1:6.3f}")
    print("\nInterpretation: results describe only this small synthetic regression corpus.")
    print("Do not generalize these numbers to patient reports or clinical accuracy.")

if __name__ == "__main__":
    main()
