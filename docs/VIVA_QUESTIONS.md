# HealthScan AI — Viva Questions and Answers

Use these to prepare for the demonstration. Explain what the code really does; do not claim OCR, a trained medical NER model, diagnostic performance, or clinical validation unless you implement and measure them.

## Project overview

### 1. What is HealthScan AI?
It is a full-stack health-information dashboard that reads selectable text from medical PDFs, extracts supported vital signs, optionally asks Gemini to explain the report, stores records in MySQL, visualizes saved readings, and compares saved reports.

### 2. What problem does it solve?
It brings source text, structured measurements, explanations, and historical records into one interface rather than requiring values to be copied across separate tools.

### 3. What is the contribution beyond calling an AI API?
The project integrates PDF ingestion, transparent label-based extraction, structured persistence, longitudinal charts, report search, two-report comparison, CSV export, input validation, and a testable parser. The AI explanation is only one module.

### 4. Is the application a diagnostic system?
No. It is an informational prototype. Parsing can be wrong and AI text can be inaccurate. Users must verify values against source documents and rely on qualified professionals for medical decisions.

### 5. What are the main modules?
Frontend dashboard, PDF text extraction, vital parsing, AI explanation, MySQL persistence, trend analytics, report history/search, report comparison, CSV export, and health-literacy reference cards.

## Frontend and API

### 6. Why React?
React enables reusable components and state-driven interfaces for charts, forms, report results, and history lists.

### 7. What is Vite used for?
Vite provides the frontend development server and build tooling. It bundles React code for deployment.

### 8. What is a REST API?
It exposes resources through HTTP methods and URLs. This project uses Flask routes such as GET /api/vitals and POST /api/extract-vitals.

### 9. Why use FormData for PDF uploads?
FormData sends files as multipart form data, which Flask exposes through request.files. JSON is used for text and structured measurements.

### 10. How does the frontend handle API errors?
A common API helper parses the response and throws an error for non-success HTTP status codes. The UI then displays an error instead of silently treating the request as successful.

## PDF and vital extraction

### 11. What does PyPDF do?
PyPDF reads PDF page content and extracts selectable text. It does not automatically recognize text inside a page that contains only an image.

### 12. Why might a scanned PDF fail?
A scanned page may contain pixels instead of a text layer. OCR is required to convert those pixels into text; OCR is not currently part of this pipeline.

### 13. How does the vital extractor work?
It searches text for known labels such as heart rate, pulse, SpO₂, blood pressure, systolic/diastolic pressure and temperature, captures nearby numbers, applies broad plausibility bounds, and returns null when it cannot detect a supported value.

### 14. Why use regular expressions?
They are lightweight, deterministic, easy to explain, and straightforward to test. However, they depend on known label patterns and can fail on unfamiliar layouts.

### 15. Is regex extraction machine learning?
No. The current vital parser is rule-based text processing, not a trained ML model. A real ML extension would require a labelled dataset, train/test separation, model selection and measured evaluation.

### 16. How is temperature normalized?
When a Fahrenheit unit is detected, the parser converts it to Celsius using (F − 32) × 5 / 9 and rounds the stored value. Unit ambiguity is a known failure risk.

### 17. Why are unsupported values returned as null?
A missing measurement should remain missing rather than being invented or replaced with zero, which could be confused with a real measurement.

### 18. Can the project extract all laboratory values?
No. This version focuses on five vital fields. Lab analytes, reference intervals and other measurements require additional extraction rules and evaluation.

## AI and database

### 19. What is Gemini used for?
Gemini generates a separate plain-language explanation of report text. It is not the source of truth for numeric values and is not a clinician.

### 20. Why separate extraction from explanation?
The structured parser is deterministic and returns fields that can be checked against source text. The AI explanation is probabilistic and displayed separately so users can distinguish detected values from generated prose.

### 21. What is the database used for?
MySQL stores user account records, vital readings, report text and optional generated analysis so the dashboard can retrieve history.

### 22. What is a primary key?
A primary key uniquely identifies a row in a table. The id fields identify users, reports and vital records.

### 23. Why hash passwords?
Password hashing stores a derived value rather than the readable password. Hashing does not by itself implement session authentication or protect every API route.

### 24. What important security limitation remains?
The prototype does not fully authenticate API requests or isolate vital/report rows by user. Public deployment must not be used for confidential patient records until session authorization, per-user ownership, restricted CORS and related protections are implemented.

## Analytics and evaluation

### 25. How are trend differences calculated?
For each field, the app subtracts the earliest available numeric value from the latest available numeric value. It requires at least two values and skips missing readings. It is descriptive arithmetic, not a medical conclusion.

### 26. How does report comparison work?
It retrieves two saved report texts, runs the same extractor on each, and displays both extracted values and the numerical difference. The values must still be verified against the original PDF.

### 27. Why export CSV?
CSV is portable and can be opened in spreadsheet software for further analysis or as a simple copy of saved vital history.

### 28. How would you evaluate the extractor?
Prepare a representative labelled dataset, manually verify true values against source documents, and compute per-field precision, recall and F1 plus exact-match accuracy. Keep a held-out test set separate from examples used to tune rules.

### 29. Define precision, recall and F1.
Precision is TP / (TP + FP) and measures how many extracted results were correct. Recall is TP / (TP + FN) and measures how many present target values were found. F1 is the harmonic mean 2PR / (P + R).

### 30. Are unit tests enough to prove medical accuracy?
No. Unit tests check known software cases. Representative, privacy-safe, manually labelled documents are needed to estimate extraction performance, and clinical deployment would require much more validation and governance.

### 31. Why include numeric plausibility bounds?
They reject obvious parsing artifacts, such as a three-digit oxygen saturation above 100. These limits catch only some errors; they do not prove that a value is correct or medically safe.

### 32. What are the biggest limitations?
Scanned PDFs require OCR; unfamiliar labels and layouts can defeat regex; the AI may be wrong; trends lack full clinical context; the API needs per-user authorization; and no clinical accuracy result should be claimed without an evaluation.

### 33. What would you improve next?
Add OCR, enforce authenticated per-user data isolation, build API and frontend integration tests, label a diverse privacy-safe evaluation corpus, record extraction provenance, and consider a medical NER model only if its data and evaluation can be justified.

### 34. What happens if Gemini is unavailable?
The backend can try configured fallback models for temporary capacity errors. If no model succeeds, the API returns an error; vital parsing and already-extracted text are separate steps.

### 35. What should you demonstrate in the viva?
Use a fictional/sample PDF, show source text, extract vitals, review and save values, show trend charts, search report history, compare two saved sample reports, export a CSV, and explain a parser test and one privacy limitation. Never demonstrate using another person's real medical data.
