# HealthScan AI — Minor Project Report

> **Project status:** This report describes the implemented design and an evaluation plan. Record actual test counts and metrics only after running the tests against manually labelled reports. Do not report invented accuracy percentages.

## 1. Abstract

HealthScan AI is a full-stack health-information dashboard combining medical PDF text extraction, rule-based vital-sign extraction, AI-assisted report explanation, historical storage, longitudinal visualization, and report comparison. A user uploads a text-based PDF; the backend reads selectable text with PyPDF, detects supported measurements using label-aware regular expressions, and can request a separate plain-language explanation from Google Gemini. Users can manually enter readings, review saved report history, compare extracted vital measurements across two reports, and export saved vital records to CSV.

The application is an educational information-management prototype. It does not diagnose disease, prescribe treatment, or replace assessment by a qualified healthcare professional.

## 2. Problem statement

Medical reports contain dense text, abbreviations, numerical measurements, and reference intervals. Reviewing multiple reports over time can be inconvenient, and manually copying values into separate notes or spreadsheets can fragment the information. A useful student project should make source text accessible, separate detected measurements from AI-generated explanations, preserve a way to verify the source, and provide transparent visual summaries.

## 3. Objectives

1. Extract selectable text from uploaded PDF reports.
2. Detect heart rate, oxygen saturation, systolic blood pressure, diastolic blood pressure, and temperature.
3. Implement and evaluate an experimental supervised ML classifier for vital-related report lines alongside a deterministic baseline.
4. Normalize Fahrenheit temperature to Celsius for consistent storage.
5. Generate an optional AI-assisted explanation in everyday language while stating uncertainty.
6. Save manually entered or reviewed extracted readings in MySQL.
7. Visualize saved readings and calculate first-to-latest differences.
8. Maintain searchable report history and compare two reports using the same extraction rules.
9. Support CSV export and provide health-literacy reference material.
10. Test parser edge cases and document safety and privacy limitations.

## 4. Existing/manual approach and proposed approach

### Existing/manual approach
- Users open PDFs and manually find values.
- Measurements are copied into separate notes or spreadsheets.
- Changes between reports must be calculated manually.
- Technical report language can be difficult to understand.

### Proposed HealthScan AI approach
- A React dashboard provides report ingestion, data entry, history, charts, report comparison, and export.
- A Flask REST API uses PyPDF to extract selectable PDF text.
- A deterministic, label-aware parser detects supported vital fields and returns null when a measurement is not found.
- An experimental supervised ML classifier using TF-IDF character n-grams and logistic regression labels each report line as one of seven categories. A constrained parser then extracts a number only for the predicted category.
- The rule-based extractor and ML extractor can be run separately for a demonstration and comparison. Neither can claim medical accuracy without a real labelled evaluation.
- A separate Gemini API call generates a plain-language explanation of report text. It is not treated as the source of extracted measurements.
- MySQL stores report and vital records when the database is available.
- Analytics summarizes saved values without claiming that a trend is a diagnosis.

## 5. System architecture

~~~mermaid
flowchart TD
    U[User] --> UI[React + Vite Dashboard]
    UI --> API[Flask REST API]
    API --> PDF[PyPDF Text Extraction]
    PDF --> TXT[Extracted Source Text]
    TXT --> REGEX[Label-aware Vital Parser]
    TXT --> GEMINI[Gemini Explanation Service]
    REGEX --> RESULTS[Reviewable Vital Cards]
    GEMINI --> EXPLAIN[Plain-language Explanation]
    RESULTS --> REVIEW[User Verifies Source Values]
    REVIEW --> DB[(MySQL)]
    API --> DB
    DB --> HISTORY[Report and Vital History]
    HISTORY --> CHARTS[Trend Charts, Report Comparison, CSV Export]
~~~

## 6. Technology stack

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React, Vite, CSS | Dashboard, forms, charts, report library, comparison and export |
| API | Python, Flask | HTTP endpoints, validation, file handling and orchestration |
| PDF processing | PyPDF | Extract selectable text from PDF pages |
| Vital parsing baseline | Python regular expressions | Find values near supported labels, apply broad numeric bounds and normalize temperature |
| Supervised ML | scikit-learn: TfidfVectorizer + LogisticRegression | Classify report lines into vital categories and unrelated text |
| AI explanation | Google Gemini API using google-genai | Produce a separate plain-language explanation |
| Database | MySQL | Store users, vital readings, report text and generated analysis |
| Deployment | Vercel, Render, managed MySQL | Host frontend, backend and database |

## 7. Main modules

### 7.1 Dashboard and input validation
The dashboard displays the latest saved values and provides a manual-entry form. Basic numeric bounds reduce obvious entry mistakes. They are not medical safety checks.

### 7.2 PDF text extraction
The upload endpoint accepts PDF files within the configured size limit. PyPDF reads selectable text from each page. Image-only scanned PDFs may contain no text layer; optical character recognition (OCR) is a future enhancement.

### 7.3 Vital-sign extraction
The parser looks for labels and nearby values. Supported fields include heart rate, SpO₂, combined blood pressure or separate systolic/diastolic labels, and temperature. Fahrenheit values are converted to Celsius. Values outside broad plausibility bounds are omitted instead of returned. The parser may miss unfamiliar layouts or match a nearby number incorrectly; results must be reviewed against the original document.

### 7.4 Experimental supervised ML vital-line classifier

The ML endpoint (/api/ml-extract-vitals) uses character n-gram TF-IDF features followed by logistic regression to classify each non-empty line into one of seven labels: heart rate, SpO₂, combined blood pressure, systolic blood pressure, diastolic blood pressure, temperature, or other text. Character n-grams learn patterns in word fragments and abbreviations without requiring a large language model.

The starter corpus is available in backend/data/vital_line_dataset.csv and contains authored synthetic line/label examples. A separate synthetic holdout file (backend/data/vital_line_eval.csv) is used by the evaluation script. The model trains lazily on the first ML extraction request in each backend worker process and caches the fitted classifier in memory for later requests.

After classification, a constrained parser attempts to extract a supported number only from the corresponding line and category. The result includes a source snippet, predicted label, class probability, number of detected fields, and low-confidence lines skipped. The displayed confidence score is not a calibrated probability that the vital value is correct.

This is an ML experiment, not a medical NER model trained on actual patient records. Synthetic examples demonstrate the pipeline, but can produce misleadingly strong evaluation scores. Real-world claims require a larger independently labelled and privacy-safe evaluation corpus.

### 7.5 AI-assisted explanation
The explanation service uses a separate request to Gemini and instructs it not to invent values, diagnose conditions, prescribe medication, or label a value high or low without supporting report evidence. AI output is probabilistic and may be incomplete or inaccurate.

### 7.6 History and persistence
MySQL tables store vital readings and uploaded reports. The report library supports keyword search and loading a saved report back into the analysis workflow. Database availability affects whether reports and their explanations can be persisted.

### 7.7 Trend analytics
Charts use saved numeric records. The trend summary calculates the difference between the first and latest available numeric measurements for each field. A direction or difference describes recorded data; it does not establish whether a person's health is improving or worsening.

### 7.8 Report comparison
The comparison module runs the same vital parser on two saved report texts and presents the extracted values and arithmetic differences in a table. Users are reminded to confirm both values against their source documents.

### 7.9 Export and health-literacy guide
Users can export stored vital history as CSV and print/save a page summary. Health-literacy cards describe broad adult reference points with caveats about individual context; they are not personalized medical advice.

## 8. Algorithms

### Vital extraction algorithm

1. Receive extracted PDF text.
2. Check that the text is a non-empty string and below the configured maximum length.
3. Search for supported labels using case-insensitive regular expressions.
4. Parse the numeric capture associated with each label.
5. Apply field-specific plausibility bounds to reject obvious parsing artifacts.
6. Convert Fahrenheit temperature to Celsius.
7. Return structured fields and use null when no supported value was identified.
8. Show the detected values and ask the user to verify them against the report.
9. Save values only after an explicit user action.

### Trend calculation

For a field with available numeric readings in chronological order:

**change = latest available value − earliest available value**

At least two numeric readings are required. Missing values are skipped. This statistic does not account for sampling frequency, measurement conditions, uncertainty, or causal relationships.

## 9. Database design

### users
Stores an identifier, name, email, password hash, and creation timestamp. The current API includes signup and login endpoints, but complete authenticated sessions and per-user authorization must be added before sensitive records are used.

### vitals
Stores an identifier, heart rate, SpO₂, systolic BP, diastolic BP, temperature in Celsius, and recorded timestamp.

### reports
Stores an identifier, filename, extracted report text, optional AI explanation, and upload timestamp.

**Important implementation limitation:** the current prototype's vital and report endpoints are not fully isolated by authenticated user. Do not upload real patient records or use the public deployment for confidential medical data. Add authentication, per-user foreign keys and authorization checks before production use.

## 10. API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/health | API health check |
| GET | /api/db-test | Database connectivity check |
| POST | /api/signup | Create an account record |
| POST | /api/login | Verify account credentials |
| GET / POST | /api/vitals | Read or store a measurement |
| GET | /api/reports | Retrieve saved report history |
| POST | /api/upload-report | Upload PDF and extract selectable text |
| POST | /api/extract-vitals | Parse supported values from report text using rules |
| POST | /api/ml-extract-vitals | Experimental supervised ML line classification and value extraction |
| POST | /api/analyze-report | Request a Gemini explanation |
| PUT | /api/reports/{report_id}/analysis | Save or update explanation text |

## 11. Testing and evaluation plan

Run backend unit tests from the backend directory:

~~~bash
python -m unittest discover -s tests -v
~~~

The regression suite covers common labels, abbreviations, separate blood-pressure labels, Fahrenheit conversion, missing values, partial results, invalid numeric values, and invalid input types. Test outcomes must be recorded from actual execution.

### Evaluation on a labelled report set

Prepare a held-out set of report snippets whose true values have been manually verified against their source documents. Keep report templates from the test set separate from examples used to tune parsing rules.

For each field, count:
- **True positive (TP):** extractor found the correct value.
- **False positive (FP):** extractor returned a wrong or unsupported value.
- **False negative (FN):** a present, supported value was missed.

Calculate:
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 × Precision × Recall / (Precision + Recall)

Also record exact-match accuracy per field, units, report layout, missing-value handling, and failure examples. If a denominator is zero, report the metric as undefined. The current synthetic corpus happens to achieve 100% field-level agreement because it consists of a small set of authored examples; this must not be presented as accuracy on real reports. Unit tests are software regression checks, not a substitute for representative evaluation. The completed CI run for commit 0a6ef1b reported 19 passing backend tests and passed the synthetic evaluation step.

| Evaluation item | Observed result |
|---|---|
| Automated backend tests | 19 tests passed in the completed CI run at commit 0a6ef1b |
| Synthetic regression corpus | 9 authored text snippets; not clinical or real-world reports |
| Field-level exact agreement | 100.0% on those 9 synthetic examples only |
| Heart-rate precision / recall / F1 | 1.000 / 1.000 / 1.000 on synthetic examples |
| SpO₂ precision / recall / F1 | 1.000 / 1.000 / 1.000 on synthetic examples |
| Systolic BP precision / recall / F1 | 1.000 / 1.000 / 1.000 on synthetic examples |
| Diastolic BP precision / recall / F1 | 1.000 / 1.000 / 1.000 on synthetic examples |
| Temperature precision / recall / F1 | 1.000 / 1.000 / 1.000 on synthetic examples |
| Held-out real-world report evaluation | Not performed |
| Known failure cases | Scanned PDFs without OCR, unfamiliar labels, ambiguous units, and numbers incorrectly associated with nearby labels |

### Supervised ML line-classification evaluation

Run from the backend directory:

~~~bash
python evaluate_ml_classifier.py
~~~

The script trains on backend/data/vital_line_dataset.csv and evaluates seven-way line labels using the separate backend/data/vital_line_eval.csv file. It reports line-label accuracy, per-class precision/recall/F1 and a confusion matrix. The holdout contains authored synthetic examples rather than actual medical reports. Treat the numbers only as a check that the model learns the small authored classification task; they are not extraction accuracy or clinical accuracy. Keep the holdout separate from further rule/model tuning and replace it with independently labelled, privacy-safe examples before making generalization claims.

## 12. Security, privacy and responsible use

- Keep API keys, database passwords and CA certificates in server-side environment variables or secret files.
- Do not commit environment files or real patient PDFs to source control.
- Restrict CORS to known frontend origins in deployment.
- Add session/token authentication, per-user data ownership and authorization before real patient data is considered.
- Avoid logging report contents or secrets.
- Validate uploaded files and size limits. Consider malware scanning and stricter PDF protections for public use.
- Display source values and generated explanation separately.
- Do not use the system for diagnosis, medication decisions or emergency triage.

## 13. Limitations

1. PyPDF extracts selectable text; scanned PDFs require OCR.
2. Report formatting and abbreviations vary, and regex is not robust to every layout.
3. Plausibility checks are not clinical validation.
4. AI-generated text may omit details or introduce errors.
5. The current prototype lacks complete per-user authorization.
6. The deployment depends on external AI service, database availability and provider quotas.
7. The trend calculation does not account for irregular dates or clinical context.

## 14. Future scope

- Add OCR for scanned reports and an OCR-confidence indicator.
- Add authenticated sessions, row-level user ownership, consent, audit logging and access controls.
- Evaluate the starter classifier on a larger, independently labelled and privacy-safe set of real report snippets; compare it with the rule-based baseline.
- Explore medical named-entity recognition or layout-aware models only if a suitable labelled corpus, train/test separation, compute budget and evaluation plan are available.
- Add robust unit conversion and provenance for every extracted field.
- Add automated API and frontend integration tests.
- Support downloadable report summaries and user-controlled data deletion.

## 15. Conclusion

HealthScan AI demonstrates an integrated workflow across PDF processing, rule-based parsing, supervised ML line classification, AI-assisted explanation, relational storage, visualization, report history and report comparison. Its purpose is to make report data easier to inspect and track while keeping source values, model predictions, calculated trends and AI-generated prose distinct. The starter classifier demonstrates an end-to-end supervised ML pipeline, but its synthetic corpus cannot establish performance on real reports. The next priorities are independent real-report evaluation and stronger data protection before any real health information is used.

## 16. References

- PyPDF documentation: https://pypdf.readthedocs.io/
- Flask documentation: https://flask.palletsprojects.com/
- React documentation: https://react.dev/
- Vite documentation: https://vite.dev/
- Recharts documentation: https://recharts.org/
- Google Gemini API documentation: https://ai.google.dev/gemini-api/docs
- MySQL documentation: https://dev.mysql.com/doc/
