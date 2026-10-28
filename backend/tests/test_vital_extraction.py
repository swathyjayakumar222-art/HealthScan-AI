"""Regression tests for HealthScan AI's rule-based vital extractor.

Run from backend/ with:
    python -m unittest discover -s tests -v

These tests validate text parsing only; they do not establish clinical accuracy.
"""
import unittest

from app import app, extract_vitals_from_text


class VitalExtractionTests(unittest.TestCase):
    def test_standard_report_labels(self):
        text = """
        Patient observations
        Heart Rate: 72 bpm
        SpO2: 98%
        Blood Pressure: 120/80 mmHg
        Temperature: 36.8 C
        """
        self.assertEqual(
            extract_vitals_from_text(text),
            {
                "heart_rate": 72,
                "spo2": 98,
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "temperature": 36.8,
            },
        )

    def test_common_abbreviations_and_fahrenheit(self):
        text = "HR (bpm) = 84; O2 saturation: 97%; BP (mmHg) 118/76; Temp: 98.6 F"
        result = extract_vitals_from_text(text)
        self.assertEqual(result["heart_rate"], 84)
        self.assertEqual(result["spo2"], 97)
        self.assertEqual(result["systolic_bp"], 118)
        self.assertEqual(result["diastolic_bp"], 76)
        self.assertEqual(result["temperature"], 37.0)

    def test_pulse_and_separate_blood_pressure_labels(self):
        text = "Pulse Rate - 68 bpm\nSystolic BP: 124\nDiastolic BP: 81\nBody temperature: 37.1 °C"
        result = extract_vitals_from_text(text)
        self.assertEqual(result["heart_rate"], 68)
        self.assertEqual(result["systolic_bp"], 124)
        self.assertEqual(result["diastolic_bp"], 81)
        self.assertEqual(result["temperature"], 37.1)

    def test_spaced_spo2_label(self):
        result = extract_vitals_from_text("Oxygen saturation: 96 percent; SPO 2 = 98%")
        self.assertEqual(result["spo2"], 96)

    def test_no_measurements_returns_null_values(self):
        result = extract_vitals_from_text("Patient presents for follow-up. No vitals included.")
        self.assertTrue(all(value is None for value in result.values()))

    def test_non_string_input_is_rejected(self):
        with self.assertRaises(TypeError):
            extract_vitals_from_text(None)

    def test_impossible_values_are_not_returned(self):
        result = extract_vitals_from_text(
            "Heart rate: 999\nSpO2: 198%\nBP: 999/999\nTemperature: 99 C"
        )
        self.assertIsNone(result["heart_rate"])
        self.assertIsNone(result["spo2"])
        self.assertIsNone(result["systolic_bp"])
        self.assertIsNone(result["diastolic_bp"])
        self.assertIsNone(result["temperature"])

    def test_temperature_is_normalized_to_celsius(self):
        result = extract_vitals_from_text("Body temperature = 100.4°F")
        self.assertEqual(result["temperature"], 38.0)

    def test_api_includes_source_evidence_and_quality_metadata(self):
        client = app.test_client()
        response = client.post(
            "/api/extract-vitals",
            json={"text": "Heart Rate: 72 bpm\nSpO2: 98%\nBP: 120/80\nTemperature: 36.8 C"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["vitals"]["heart_rate"], 72)
        self.assertIn("heart_rate", body["evidence"])
        self.assertIn("snippet", body["evidence"]["heart_rate"])
        self.assertEqual(body["quality"]["fields_found"], 5)
        self.assertIn("coverage_percent", body["quality"])

    def test_api_rejects_overlong_text(self):
        client = app.test_client()
        response = client.post("/api/extract-vitals", json={"text": "x" * 250001})
        self.assertEqual(response.status_code, 413)

    def test_partial_values_do_not_invent_missing_measurements(self):
        result = extract_vitals_from_text("Heart rate: 77 bpm; SpO2: 97%")
        self.assertEqual(result["heart_rate"], 77)
        self.assertEqual(result["spo2"], 97)
        self.assertIsNone(result["systolic_bp"])
        self.assertIsNone(result["diastolic_bp"])
        self.assertIsNone(result["temperature"])


if __name__ == "__main__":
    unittest.main()
