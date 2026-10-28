import unittest

from vital_extractor import extract_vitals


class VitalExtractorTests(unittest.TestCase):
    def test_extracts_common_report_layout(self):
        result = extract_vitals(
            "Heart Rate: 72 bpm\nSpO2: 98%\nBlood Pressure: 120/80 mmHg\nTemperature: 36.8 C"
        )
        self.assertEqual(result["vitals"]["heart_rate"], 72)
        self.assertEqual(result["vitals"]["spo2"], 98)
        self.assertEqual(result["vitals"]["systolic_bp"], 120)
        self.assertEqual(result["vitals"]["diastolic_bp"], 80)
        self.assertEqual(result["vitals"]["temperature"], 36.8)

    def test_normalizes_fahrenheit_to_celsius(self):
        result = extract_vitals("Body temperature: 98.6 F")
        self.assertAlmostEqual(result["vitals"]["temperature"], 37.0, places=1)

    def test_supports_alternative_labels(self):
        result = extract_vitals("Pulse rate: 64 beats/min\nO2 sat: 97%")
        self.assertEqual(result["vitals"]["heart_rate"], 64)
        self.assertEqual(result["vitals"]["spo2"], 97)

    def test_supports_separate_blood_pressure_fields(self):
        result = extract_vitals("Systolic: 135 mmHg\nDiastolic: 85 mmHg")
        self.assertEqual(result["vitals"]["systolic_bp"], 135)
        self.assertEqual(result["vitals"]["diastolic_bp"], 85)

    def test_does_not_treat_unlabelled_numbers_as_vitals(self):
        result = extract_vitals("Patient age 42 years. Lab number 120. Appointment 2026-10-28.")
        self.assertTrue(all(value is None for value in result["vitals"].values()))

    def test_returns_traceable_source_evidence(self):
        result = extract_vitals("Heart Rate: 72 bpm")
        self.assertEqual(result["evidence"]["heart_rate"]["snippet"], "Heart Rate: 72 bpm")
        self.assertIn("rule", result["evidence"]["heart_rate"])
        self.assertEqual(result["quality"]["fields_found"], 1)

    def test_flags_parse_bound_issues_without_silent_clamping(self):
        result = extract_vitals("SpO2: 120%")
        self.assertEqual(result["vitals"]["spo2"], 120)
        self.assertTrue(any(note["field"] == "spo2" for note in result["validation_notes"]))

    def test_empty_input_returns_structured_empty_result(self):
        result = extract_vitals("")
        self.assertEqual(result["quality"]["fields_found"], 0)
        self.assertEqual(result["quality"]["coverage_percent"], 0.0)
        self.assertEqual(set(result["vitals"]), {
            "heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature"
        })


if __name__ == "__main__":
    unittest.main()
