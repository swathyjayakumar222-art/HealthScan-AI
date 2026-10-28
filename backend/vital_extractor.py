"""Explainable vital extraction for HealthScan AI.

This is a deterministic, auditable extraction layer, not a clinical model.
It returns parsed values alongside the exact source line and the rule that
matched so the user can verify every result against the original report.
"""
from __future__ import annotations

import re
from typing import Any

FIELDS = ("heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature")
FIELD_LABELS = {
    "heart_rate": "Heart rate",
    "spo2": "Blood oxygen (SpO2)",
    "systolic_bp": "Systolic blood pressure",
    "diastolic_bp": "Diastolic blood pressure",
    "temperature": "Temperature",
}
# Broad parsing sanity bounds only. These are NOT clinical reference ranges.
PARSE_BOUNDS = {
    "heart_rate": (20, 250),
    "spo2": (50, 100),
    "systolic_bp": (30, 300),
    "diastolic_bp": (20, 200),
    "temperature": (25, 45),  # normalized to Celsius
}

# Patterns require nearby labels to reduce the chance of treating unrelated
# numbers (for example age, date, or lab result IDs) as vital measurements.
PATTERNS = {
    "heart_rate": [
        (re.compile(r"\b(?:heart\s*rate|pulse(?:\s*rate)?|hr)\b\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})(?:\s*(?:bpm|beats\s*/?\s*min))?\b", re.I), "labelled heart-rate/pulse pattern"),
    ],
    "spo2": [
        (re.compile(r"\b(?:spo\s*2|spo2|oxygen\s*saturation|o2\s*(?:sat|saturation))\b\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{1,3})\s*%?\b", re.I), "labelled oxygen-saturation pattern"),
    ],
    "blood_pressure": [
        (re.compile(r"\b(?:blood\s*pressure|bp)\b\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})\s*/\s*(\d{2,3})\b", re.I), "paired blood-pressure pattern"),
    ],
    "systolic_bp": [
        (re.compile(r"\bsystolic(?:\s*(?:blood\s*pressure|bp))?\b\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})\b", re.I), "labelled systolic pattern"),
    ],
    "diastolic_bp": [
        (re.compile(r"\bdiastolic(?:\s*(?:blood\s*pressure|bp))?\b\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})\b", re.I), "labelled diastolic pattern"),
    ],
    "temperature": [
        (re.compile(r"\b(?:body\s*)?(?:temperature|temp)\b\s*(?:\(\s*°?\s*([CF])\s*\))?\s*(?:[:=\-]\s*)?(\d{2,3}(?:\.\d+)?)\s*°?\s*([CF])?\b", re.I), "labelled temperature pattern"),
    ],
}

def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]

def _first_match(lines: list[str], patterns: list[tuple[re.Pattern, str]]) -> tuple[re.Match | None, str | None, str | None]:
    for line in lines:
        for pattern, rule in patterns:
            match = pattern.search(line)
            if match:
                return match, line, rule
    return None, None, None

def extract_vitals(text: str) -> dict[str, Any]:
    """Return values, source evidence, parse-quality metadata and sanity notes."""
    if not isinstance(text, str):
        text = ""
    lines = _lines(text)
    values: dict[str, int | float | None] = {field: None for field in FIELDS}
    evidence: dict[str, dict[str, str]] = {}

    match, line, rule = _first_match(lines, PATTERNS["heart_rate"])
    if match:
        values["heart_rate"] = int(match.group(1))
        evidence["heart_rate"] = {"snippet": line, "rule": rule or "", "confidence": "label match"}

    match, line, rule = _first_match(lines, PATTERNS["spo2"])
    if match:
        values["spo2"] = int(match.group(1))
        evidence["spo2"] = {"snippet": line, "rule": rule or "", "confidence": "label match"}

    bp_match, bp_line, bp_rule = _first_match(lines, PATTERNS["blood_pressure"])
    if bp_match:
        values["systolic_bp"] = int(bp_match.group(1))
        values["diastolic_bp"] = int(bp_match.group(2))
        shared = {"snippet": bp_line or "", "rule": bp_rule or "", "confidence": "paired label match"}
        evidence["systolic_bp"] = dict(shared)
        evidence["diastolic_bp"] = dict(shared)
    else:
        for field in ("systolic_bp", "diastolic_bp"):
            match, line, rule = _first_match(lines, PATTERNS[field])
            if match:
                values[field] = int(match.group(1))
                evidence[field] = {"snippet": line, "rule": rule or "", "confidence": "label match"}

    match, line, rule = _first_match(lines, PATTERNS["temperature"])
    if match:
        value = float(match.group(2))
        unit = (match.group(3) or match.group(1) or "C").upper()
        if unit == "F":
            value = (value - 32) * 5 / 9
        values["temperature"] = round(value, 2)
        evidence["temperature"] = {
            "snippet": line,
            "rule": rule or "",
            "confidence": "label and unit match" if (match.group(1) or match.group(3)) else "label match; Celsius assumed when no unit is printed",
        }

    validation_notes = []
    for field, value in values.items():
        if value is None:
            continue
        lower, upper = PARSE_BOUNDS[field]
        if not lower <= float(value) <= upper:
            validation_notes.append({
                "field": field,
                "label": FIELD_LABELS[field],
                "value": value,
                "message": f"This parsed value is outside the engine's broad format-check bounds ({lower}–{upper}). Verify the source line and units.",
            })

    found_count = sum(value is not None for value in values.values())
    words = re.findall(r"\b[\w.%-]+\b", text)
    quality = {
        "character_count": len(text),
        "word_count": len(words),
        "nonempty_lines": len(lines),
        "fields_found": found_count,
        "fields_supported": len(FIELDS),
        "coverage_percent": round(found_count / len(FIELDS) * 100, 1),
        "method": "Explainable label-based pattern matching",
        "note": "Coverage measures supported fields found, not clinical accuracy.",
    }
    return {
        "vitals": values,
        "evidence": evidence,
        "quality": quality,
        "validation_notes": validation_notes,
        "engine": "HealthScan Explainable Extractor v2",
    }
