"""Tests for the experimental supervised ML vital-line classifier.

Run from backend/:
    python -m unittest discover -s tests -v

The corpus is synthetic and these tests do not establish medical accuracy.
"""
import unittest

from app import app
from ml_vital_extractor import extract_vitals_ml, get_classifier, read_training_rows


class MLVitalExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = get_classifier()

    def test_training_corpus_has_all_seven_classes(self):
        rows = read_training_rows()
        self.assertGreaterEqual(len(rows), 90)
        self.assertEqual(
            set(label for _, label in rows),
            {"heart_rate", "spo2", "blood_pressure", "systolic_bp",
             "diastolic_bp", "temperature", "other"},
        )

    def test_model_classifies_common_vital_lines(self):
        cases = {
            "Heart Rate: 74 bpm": "heart_rate",
            "Oxygen saturation = 94 percent": "spo2",
            "BP (mmHg) 117/75": "blood_pressure",
            "Systolic BP reading: 128": "systolic_bp",
            "Diastolic pressure was 83": "diastolic_bp",
            "Body temp: 36.9 °C": "temperature",
            "Patient weight: 72 kg": "other",
        }
        for line, expected in cases.items():
            with self.subTest(line=line):
                predicted = self.model.predict([line])[0]
                self.assertEqual(predicted, expected)

    def test_extracts_values_with_source_evidence(self):
        result = extract_vitals_ml(
            "Heart Rate: 72 bpm\n"
            "SpO2: 98%\n"
            "Blood Pressure: 120/80 mmHg\n"
            "Temperature: 36.8 C",
            confidence_threshold=0.0,
        )
        self.assertEqual(result["vitals"]["heart_rate"], 72)
        self.assertEqual(result["vitals"]["spo2"], 98)
        self.assertEqual(result["vitals"]["systolic_bp"], 120)
        self.assertEqual(result["vitals"]["diastolic_bp"], 80)
        self.assertEqual(result["vitals"]["temperature"], 36.8)
        self.assertIn("heart_rate", result["evidence"])
        self.assertIn("snippet", result["evidence"]["heart_rate"])
        self.assertIn("confidence", result["evidence"]["heart_rate"])
        self.assertGreater(result["quality"]["fields_found"], 0)

    def test_does_not_parse_random_unlabelled_numbers_as_vitals(self):
        result = extract_vitals_ml(
            "Patient age: 72 years\n"
            "Report identifier: 12080\n"
            "Glucose result: 110 mg/dL\n"
            "Appointment date: 2026-10-29"
        )
        self.assertTrue(all(value is None for value in result["vitals"].values()))

    def test_rejects_empty_or_overlong_text(self):
        with self.assertRaises(ValueError):
            extract_vitals_ml("")
        with self.assertRaises(ValueError):
            extract_vitals_ml("x" * 250001)

    def test_ml_api_returns_model_metadata_and_line_trace(self):
        client = app.test_client()
        response = client.post(
            "/api/ml-extract-vitals",
            json={"text": "Heart Rate: 72 bpm\nSpO2: 98%", "confidence_threshold": 0.0},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["vitals"]["heart_rate"], 72)
        self.assertEqual(body["vitals"]["spo2"], 98)
        self.assertIn("algorithm", body)
        self.assertGreater(body["training_examples"], 0)
        self.assertIn("predictions", body)
        self.assertIn("quality", body)

    def test_ml_api_validates_threshold(self):
        client = app.test_client()
        response = client.post(
            "/api/ml-extract-vitals",
            json={"text": "Heart Rate: 72 bpm", "confidence_threshold": 2.0},
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_confidence_threshold(self):
        with self.assertRaises(ValueError):
            extract_vitals_ml("Heart Rate: 72 bpm", 1.1)


if __name__ == "__main__":
    unittest.main()
