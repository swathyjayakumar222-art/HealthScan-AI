
import { useEffect, useState } from "react";
import "./App.css";

const DEFAULT_API_BASE = import.meta.env.PROD ? "https://healthscan-ai-xabx.onrender.com" : "http://127.0.0.1:5000";
const API_BASE = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE).replace(/\/+$/, "");
const API = API_BASE.endsWith("/api") ? API_BASE : `${API_BASE}/api`;

async function readApiResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.error || data.message || `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return data;
}

function normalizeVitals(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.vitals)) return data.vitals;
  if (Array.isArray(data?.readings)) return data.readings;
  return [];
}

const ANALYSIS_HEADINGS = [
  "Report Summary",
  "Important Values",
  "Values Outside the Given Reference Range",
  "Simple Explanation",
  "Questions to Ask a Doctor",
];

function splitAnalysisSections(text) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  const sections = [];
  let current = { heading: "AI explanation", body: [] };

  const findHeading = (line) => {
    const cleaned = line.trim().replace(/^#{1,6}\s*/, "").replace(/\*\*/g, "").trim();
    const withoutNumber = cleaned.replace(/^\d+[.)]\s*/, "").replace(/:$/, "").trim();
    return ANALYSIS_HEADINGS.find((heading) => heading.toLowerCase() === withoutNumber.toLowerCase());
  };

  for (const line of lines) {
    const heading = findHeading(line);
    if (heading) {
      if (current.body.some((item) => item.trim())) sections.push(current);
      current = { heading, body: [] };
    } else {
      current.body.push(line.replace(/\*\*/g, ""));
    }
  }

  if (current.body.some((item) => item.trim()) || sections.length === 0) sections.push(current);
  return sections.map((section) => ({
    heading: section.heading,
    body: section.body.join("\n").trim(),
  })).filter((section) => section.body);
}

// Clearly fictional sample values used only to preview the charts when no
// saved readings are available. These are never written to the database.
const DEMO_CHART_DATA = [
  { recorded_at: "2026-10-21T09:00:00", heart_rate: 72, spo2: 98, systolic_bp: 118, diastolic_bp: 78, temperature: 36.7 },
  { recorded_at: "2026-10-22T09:00:00", heart_rate: 76, spo2: 97, systolic_bp: 120, diastolic_bp: 80, temperature: 36.8 },
  { recorded_at: "2026-10-23T09:00:00", heart_rate: 70, spo2: 99, systolic_bp: 117, diastolic_bp: 77, temperature: 36.6 },
  { recorded_at: "2026-10-24T09:00:00", heart_rate: 74, spo2: 98, systolic_bp: 121, diastolic_bp: 79, temperature: 36.9 },
  { recorded_at: "2026-10-25T09:00:00", heart_rate: 71, spo2: 98, systolic_bp: 119, diastolic_bp: 78, temperature: 36.7 },
];


function VitalLineChart({ title, data, series, unit = "" }) {
  const width = 720;
  const height = 250;
  const pad = { top: 20, right: 24, bottom: 38, left: 48 };

  const points = data
    .map((item) => {
      const values = series.map((line) => {
        const raw = line.keys.map((key) => item?.[key]).find(
          (value) => value !== undefined && value !== null && value !== ""
        );
        const value = Number(raw);
        return Number.isFinite(value) && raw !== null && raw !== "" ? value : null;
      });
      return { item, values };
    })
    .filter((point) => point.values.some((value) => value !== null));

  const allValues = points.flatMap((point) => point.values).filter((value) => value !== null);
  const minValue = allValues.length ? Math.min(...allValues) : 0;
  const maxValue = allValues.length ? Math.max(...allValues) : 1;
  const spread = maxValue - minValue || Math.max(Math.abs(maxValue) * 0.1, 1);
  const low = minValue - spread * 0.15;
  const high = maxValue + spread * 0.15;

  const x = (index) =>
    pad.left + (points.length <= 1 ? 0 : (index / (points.length - 1)) * (width - pad.left - pad.right));
  const y = (value) =>
    height - pad.bottom - ((value - low) / (high - low)) * (height - pad.top - pad.bottom);

  const dateLabel = (item) => {
    const raw = item?.created_at ?? item?.timestamp ?? item?.date ?? item?.recorded_at;
    if (!raw) return "";
    const date = new Date(raw);
    return Number.isNaN(date.getTime())
      ? String(raw).slice(0, 10)
      : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  if (!points.length) {
    return (
      <article className="trend-chart-card">
        <h3>{title}</h3>
        <p className="empty-state">
          No numeric readings available for this chart yet.
        </p>
      </article>
    );
  }

  return (
    <article className="trend-chart-card">
      <h3>{title}</h3>
      <div className="trend-chart-scroll">
        <svg
          className="trend-chart-svg"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={`${title} trend chart`}
        >
          {[0, 1, 2, 3, 4].map((tick) => {
            const value = low + ((high - low) * tick) / 4;
            const yy = y(value);
            return (
              <g key={tick}>
                <line x1={pad.left} y1={yy} x2={width - pad.right} y2={yy} className="trend-grid-line" />
                <text x={pad.left - 8} y={yy + 4} textAnchor="end" className="trend-axis-label">
                  {Number(value.toFixed(1))}
                </text>
              </g>
            );
          })}

          {series.map((line, seriesIndex) => {
            const linePoints = points
              .map((point, index) =>
                point.values[seriesIndex] === null
                  ? null
                  : `${x(index)},${y(point.values[seriesIndex])}`
              )
              .filter(Boolean)
              .join(" ");

            return (
              <g key={line.label}>
                <polyline
                  points={linePoints}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="3"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {points.map((point, index) =>
                  point.values[seriesIndex] === null ? null : (
                    <circle
                      key={`${line.label}-${index}`}
                      cx={x(index)}
                      cy={y(point.values[seriesIndex])}
                      r="3.5"
                      fill={line.color}
                    >
                      <title>{`${line.label}: ${point.values[seriesIndex]}${unit ? ` ${unit}` : ""}`}</title>
                    </circle>
                  )
                )}
              </g>
            );
          })}

          {points.map((point, index) => {
            const showLabel =
              points.length <= 7 ||
              index === 0 ||
              index === points.length - 1 ||
              index % Math.ceil(points.length / 6) === 0;
            return showLabel ? (
              <text
                key={`date-${index}`}
                x={x(index)}
                y={height - 12}
                textAnchor="middle"
                className="trend-axis-label"
              >
                {dateLabel(point.item)}
              </text>
            ) : null;
          })}
        </svg>
      </div>
      <div className="trend-legend">
        {series.map((line) => (
          <span key={line.label}>
            <i style={{ background: line.color }} />
            {line.label}{unit ? ` (${unit})` : ""}
          </span>
        ))}
      </div>
    </article>
  );
}

function App() {
  const [vitals, setVitals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    heart_rate: "",
    spo2: "",
    systolic_bp: "",
    diastolic_bp: "",
    temperature: "",
  });

  const [report, setReport] = useState(null);
  const [reportText, setReportText] = useState("");
  const [extractedVitals, setExtractedVitals] = useState(null);
  const [analysis, setAnalysis] = useState("");
  const [reportId, setReportId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [savingExtracted, setSavingExtracted] = useState(false);

  // Keep sample chart values separate from real saved vitals.
  const isDemoChart = vitals.length === 0;
  const chartData = isDemoChart ? DEMO_CHART_DATA : vitals;

  const extractedPressure =
    extractedVitals && (extractedVitals.systolic_bp != null || extractedVitals.diastolic_bp != null)
      ? \`\${extractedVitals.systolic_bp ?? "—"}/\${extractedVitals.diastolic_bp ?? "—"}\`
      : null;
  const extractedItems = extractedVitals
    ? [
        { label: "Heart rate", value: extractedVitals.heart_rate, unit: "bpm" },
        { label: "Blood oxygen", value: extractedVitals.spo2, unit: "%" },
        { label: "Blood pressure", value: extractedPressure, unit: extractedPressure ? "mmHg" : "" },
        { label: "Temperature", value: extractedVitals.temperature, unit: "°C" },
      ]
    : [];
  const extractedCount = extractedItems.filter(
    (item) => item.value !== null && item.value !== undefined && item.value !== ""
  ).length;

  async function handleSaveExtractedVitals() {
    if (!extractedVitals || extractedCount === 0) {
      setMessage("There are no detected measurements to save.");
      return;
    }

    try {
      setSavingExtracted(true);
      const payload = {
        heart_rate: extractedVitals.heart_rate ?? null,
        spo2: extractedVitals.spo2 ?? null,
        systolic_bp: extractedVitals.systolic_bp ?? null,
        diastolic_bp: extractedVitals.diastolic_bp ?? null,
        temperature: extractedVitals.temperature ?? null,
      };
      const response = await fetch(\`\${API}/vitals\`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await readApiResponse(response);
      setMessage("Extracted measurements saved to your real vital history.");
      await fetchVitals();
    } catch (error) {
      setMessage(error.message || "Could not save extracted measurements.");
    } finally {
      setSavingExtracted(false);
    }
  }

  async function fetchVitals() {
    try {
      setLoading(true);

      const response = await fetch(`${API}/vitals`, { signal: AbortSignal.timeout(10000) });
      const data = await readApiResponse(response);
      setVitals(normalizeVitals(data));
    } catch (error) {
      setMessage(`Unable to load vitals: ${error.message || "Check the backend URL and database connection."}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchVitals();
  }, []);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  async function handleSaveVitals(event) {
    event.preventDefault();
    setMessage("");

    const payload = {};

    Object.entries(form).forEach(([key, value]) => {
      if (value !== "") {
        payload[key] = Number(value);
      }
    });

    if (Object.keys(payload).length === 0) {
      setMessage("Please enter at least one vital reading.");
      return;
    }

    try {
      setSaving(true);

      const response = await fetch(`${API}/vitals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await readApiResponse(response);

      setMessage("Vitals saved successfully!");
      setForm({
        heart_rate: "",
        spo2: "",
        systolic_bp: "",
        diastolic_bp: "",
        temperature: "",
      });

      await fetchVitals();
    } catch (error) {
      setMessage(error.message || "Error saving vitals.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUploadReport(event) {
    event.preventDefault();

    if (!report) {
      setMessage("Please select a PDF report first.");
      return;
    }

    try {
      setUploading(true);
      setMessage("");
      setReportText("");
      setExtractedVitals(null);
      setAnalysis("");
      setReportId(null);

      const formData = new FormData();
      formData.append("file", report);

      const response = await fetch(`${API}/upload-report`, {
        method: "POST",
        body: formData,
      });

      const data = await readApiResponse(response);

      setReportId(data.report_id ?? data.id ?? null);
      setReportText(data.text ?? data.extracted_text ?? "");
      setMessage(data.message || "Report uploaded successfully!");
    } catch (error) {
      setMessage(error.message || "Could not upload report.");
    } finally {
      setUploading(false);
    }
  }

  async function handleExtractVitals() {
    if (!report) {
      setMessage("Please upload a PDF report first.");
      return;
    }

    try {
      setExtracting(true);
      setMessage("");

      // The backend extract-vitals endpoint expects JSON report text,
      // which is returned by /upload-report.
      if (!reportText.trim()) {
        throw new Error("Upload the PDF first so its text can be extracted.");
      }

      const response = await fetch(`${API}/extract-vitals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: reportText }),
      });

      const data = await readApiResponse(response);

      const extracted = data.vitals ?? data.extracted_vitals ?? data;
      setExtractedVitals(extracted);

      if (data.report_id != null) {
        setReportId(data.report_id);
      }

      if (data.text) {
        setReportText(data.text);
      }

      const foundCount = Number.isFinite(data.found_count)
        ? data.found_count
        : Object.values(extracted).filter((value) => value !== null && value !== undefined && value !== "").length;
      setMessage(
        foundCount > 0
          ? `Extraction complete: ${foundCount} measurement group(s) found. Review the structured results below.`
          : "No supported vital values were detected. Check the PDF text below; scanned image PDFs may require OCR."
      );
    } catch (error) {
      setMessage(error.message || "Error extracting vitals.");
    } finally {
      setExtracting(false);
    }
  }

  async function handleAnalyzeReport() {
    const textToAnalyze = reportText.trim();

    if (!textToAnalyze) {
      setMessage(
        "Upload a report first so there is text to analyze."
      );
      return;
    }

    try {
      setAnalyzing(true);
      setMessage("");
      setAnalysis("");

      const response = await fetch(`${API}/analyze-report`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: textToAnalyze,
          report_id: reportId,
        }),
      });

      const data = await readApiResponse(response);

      setAnalysis(
        typeof data.analysis === "string"
          ? data.analysis
          : JSON.stringify(data.analysis ?? data, null, 2)
      );

      setMessage("AI explanation generated separately from the extracted measurements.");
    } catch (error) {
      setMessage(error.message || "Could not analyze the report.");
    } finally {
      setAnalyzing(false);
    }
  }

  function displayValue(value, unit = "") {
    if (value === undefined || value === null || value === "") {
      return "Not available";
    }

    return `${value}${unit}`;
  }

  function getVitalValue(vital, ...keys) {
    for (const key of keys) {
      if (vital?.[key] !== undefined && vital[key] !== null) {
        return vital[key];
      }
    }
    return null;
  }

  const latest = vitals.length > 0 ? vitals[vitals.length - 1] : null;

  const vitalCards = [
    {
      title: "Heart Rate",
      value: getVitalValue(latest, "heart_rate", "heartRate"),
      unit: " bpm",
      icon: "♥",
    },
    {
      title: "Blood Oxygen",
      value: getVitalValue(latest, "spo2", "oxygen_saturation"),
      unit: "%",
      icon: "◉",
    },
    {
      title: "Blood Pressure",
      value:
        getVitalValue(latest, "systolic_bp", "systolic") != null &&
        getVitalValue(latest, "diastolic_bp", "diastolic") != null
          ? `${getVitalValue(latest, "systolic_bp", "systolic")}/${getVitalValue(
              latest,
              "diastolic_bp",
              "diastolic"
            )}`
          : null,
      unit: " mmHg",
      icon: "＋",
    },
    {
      title: "Temperature",
      value: getVitalValue(latest, "temperature", "body_temperature"),
      unit: " °C",
      icon: "♨",
    },
  ];

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-symbol" aria-hidden="true">✚</div>
          <div className="brand-copy">
            <p className="brand-kicker">PERSONAL HEALTH INTELLIGENCE</p>
            <h1>HealthScan <span>AI</span></h1>
            <p className="brand-subtitle">Your health information, made clearer.</p>
          </div>
        </div>
        <div className="header-actions">
          <span className="dashboard-status"><i aria-hidden="true" /> Health dashboard</span>
          <button className="refresh-button" onClick={fetchVitals}>
            <span aria-hidden="true">↻</span> Refresh data
          </button>
        </div>
      </header>

      <main className="dashboard">
        <section className="welcome-section">
          <div className="welcome-copy">
            <p className="section-eyebrow">YOUR HEALTH, AT A GLANCE</p>
            <h2>A clearer picture of your health.</h2>
            <p>
              Track vital measurements, explore trends, and turn medical-report
              details into explanations that are easier to understand.
            </p>
          </div>
          <div className="welcome-illustration" aria-hidden="true">
            <span className="pulse-orbit orbit-one" />
            <span className="pulse-orbit orbit-two" />
            <span className="pulse-cross">✚</span>
            <span className="pulse-line">⌁</span>
          </div>
        </section>

        {message && (
          <div className="status-message" role="status">
            {message}
          </div>
        )}

        <section className="section">
          <div className="section-heading">
            <div>
              <h2>Health Overview</h2>
              <p>Your latest recorded vital readings</p>
            </div>
            <span className="reading-count">
              {vitals.length} readings
            </span>
          </div>

          {loading ? (
            <p className="empty-state">Loading your health data...</p>
          ) : (
            <div className="vitals-grid">
              {vitalCards.map((card) => (
                <article className="vital-card" key={card.title}>
                  <div className="vital-card-top">
                    <span className="vital-icon">{card.icon}</span>
                    <span className="vital-label">{card.title}</span>
                  </div>

                  <h3>
                    {card.value === null
                      ? "—"
                      : `${card.value}${card.unit}`}
                  </h3>
                </article>
              ))}
            </div>
          )}

          {!loading && vitals.length === 0 && (
            <p className="empty-state">
              No readings found. Add your first vital reading below.
            </p>
          )}
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <h2>Vitals Trends</h2>
              <p>Changes across your saved readings</p>
            </div>
          </div>

          {isDemoChart ? (
            <div className="demo-chart-notice" role="note">
              <strong>Demo chart preview — illustrative values only.</strong>
              <span>
                These sample values are not your health readings and are not saved.
                Your real charts will use your saved readings when they are available.
              </span>
            </div>
          ) : vitals.length < 2 ? (
            <p className="empty-state">
              One real reading is available. Add another to see how your values change over time.
            </p>
          ) : null}

          <div className="trend-chart-grid">
            <VitalLineChart
              title={isDemoChart ? "Demo preview · Heart Rate" : "Heart Rate"}
              data={chartData}
              series={[{ label: "Heart rate", keys: ["heart_rate", "heartRate"], color: "#e05260" }]}
              unit="bpm"
            />
            <VitalLineChart
              title={isDemoChart ? "Demo preview · Blood Oxygen (SpO₂)" : "Blood Oxygen (SpO₂)"}
              data={chartData}
              series={[{ label: "SpO₂", keys: ["spo2", "oxygen_saturation"], color: "#3288c8" }]}
              unit="%"
            />
            <VitalLineChart
              title={isDemoChart ? "Demo preview · Blood Pressure" : "Blood Pressure"}
              data={chartData}
              series={[
                { label: "Systolic", keys: ["systolic_bp", "systolic"], color: "#8b5cf6" },
                { label: "Diastolic", keys: ["diastolic_bp", "diastolic"], color: "#16a085" },
              ]}
              unit="mmHg"
            />
            <VitalLineChart
              title={isDemoChart ? "Demo preview · Temperature" : "Temperature"}
              data={chartData}
              series={[{ label: "Temperature", keys: ["temperature", "body_temperature"], color: "#e39b35" }]}
              unit="°C"
            />
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <h2>Add New Vitals</h2>
              <p>Enter your readings manually</p>
            </div>
          </div>

          <form className="vitals-form" onSubmit={handleSaveVitals}>
            <label>
              Heart Rate (bpm)
              <input
                type="number"
                name="heart_rate"
                min="1"
                max="300"
                value={form.heart_rate}
                onChange={handleChange}
                placeholder="e.g. 72"
              />
            </label>

            <label>
              Blood Oxygen (%)
              <input
                type="number"
                name="spo2"
                min="1"
                max="100"
                value={form.spo2}
                onChange={handleChange}
                placeholder="e.g. 98"
              />
            </label>

            <label>
              Systolic BP (mmHg)
              <input
                type="number"
                name="systolic_bp"
                min="1"
                max="300"
                value={form.systolic_bp}
                onChange={handleChange}
                placeholder="e.g. 120"
              />
            </label>

            <label>
              Diastolic BP (mmHg)
              <input
                type="number"
                name="diastolic_bp"
                min="1"
                max="200"
                value={form.diastolic_bp}
                onChange={handleChange}
                placeholder="e.g. 80"
              />
            </label>

            <label>
              Temperature (°C)
              <input
                type="number"
                name="temperature"
                step="0.1"
                min="25"
                max="45"
                value={form.temperature}
                onChange={handleChange}
                placeholder="e.g. 36.8"
              />
            </label>

            <button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save Vitals"}
            </button>
          </form>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <h2>Medical report lab</h2>
              <p>Two separate outputs: structured vital extraction and an AI-generated explanation</p>
            </div>
          </div>

          <form className="report-form" onSubmit={handleUploadReport}>
            <label className="file-label">
              Select Medical Report (PDF)
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={(event) => {
                  setReport(event.target.files?.[0] ?? null);
                  setReportText("");
                  setExtractedVitals(null);
                  setAnalysis("");
                  setReportId(null);
                }}
              />
            </label>

            {report && (
              <p className="selected-file">
                Selected file: {report.name}
              </p>
            )}

            <button className="primary-button" type="submit" disabled={uploading || !report}>
              {uploading ? "Reading PDF…" : "1. Upload & read PDF"}
            </button>
          </form>

          <div className="report-actions">
            <button
              type="button"
              onClick={handleExtractVitals}
              disabled={extracting || !report}
            >
              {extracting ? "Detecting measurements…" : "2. Extract vital measurements"}
            </button>

            <button
              type="button"
              onClick={handleAnalyzeReport}
              disabled={analyzing || !reportText.trim()}
            >
              {analyzing ? "Generating explanation…" : "3. Explain report with AI"}
            </button>
          </div>

          {extractedVitals && (
            <div className="result-panel extraction-panel">
              <div className="result-heading">
                <div className="result-icon extraction-icon" aria-hidden="true">⌁</div>
                <div>
                  <p className="result-kicker">STRUCTURED DATA</p>
                  <h3>Extracted measurements</h3>
                  <p className="result-description">Values detected directly from the text of your PDF. This is data extraction, not an AI interpretation.</p>
                </div>
                <span className="result-count">{extractedCount} of 4 found</span>
              </div>

              {extractedCount > 0 ? (
                <div className="extracted-vitals-grid">
                  {extractedItems.map((item) => (
                    <article className={item.value === null || item.value === undefined || item.value === "" ? "extracted-vital missing" : "extracted-vital"} key={item.label}>
                      <span className="extracted-vital-label">{item.label}</span>
                      <strong>
                        {item.value === null || item.value === undefined || item.value === ""
                          ? "Not found"
                          : item.value}
                        {item.value !== null && item.value !== undefined && item.value !== "" && item.unit ? <small>{item.unit}</small> : null}
                      </strong>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="no-extraction-state">
                  <strong>No supported vital values were found.</strong>
                  <p>Check the original PDF text below. If the PDF is a scanned image rather than selectable text, OCR may be required.</p>
                </div>
              )}

              {extractedCount > 0 && (
                <button className="secondary-button save-extracted-button" type="button" onClick={handleSaveExtractedVitals} disabled={savingExtracted}>
                  {savingExtracted ? "Saving measurements…" : "Save measurements to vital history"}
                </button>
              )}
            </div>
          )}

          {reportText && (
            <details className="result-panel report-text-panel">
              <summary>
                <span>Original text extracted from PDF</span>
                <small>Source text · reference only</small>
              </summary>
              <pre>{reportText}</pre>
            </details>
          )}

          {analysis && (
            <div className="result-panel ai-analysis-panel">
              <div className="result-heading">
                <div className="result-icon analysis-icon" aria-hidden="true">✧</div>
                <div>
                  <p className="result-kicker">AI-POWERED EXPLANATION</p>
                  <h3>Understanding your report</h3>
                  <p className="result-description">A contextual explanation generated by AI. It is different from the structured measurements above and is not a diagnosis.</p>
                </div>
              </div>
              <div className="analysis-sections">
                {splitAnalysisSections(analysis).map((section, index) => (
                  <article className="analysis-section-card" key={section.heading || index}>
                    <h4>{section.heading}</h4>
                    <p>{section.body}</p>
                  </article>
                ))}
              </div>
              <p className="disclaimer">
                This explanation is for general understanding only. It may contain errors and does not replace advice from a qualified healthcare professional. Seek professional care for medical concerns.
              </p>
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <h2>Recent Readings</h2>
              <p>Your saved vital readings</p>
            </div>
          </div>

          {loading ? (
            <p className="empty-state">Loading readings...</p>
          ) : vitals.length === 0 ? (
            <p className="empty-state">No readings recorded yet.</p>
          ) : (
            <div className="table-wrapper">
              <table className="vitals-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Heart Rate</th>
                    <th>SpO₂</th>
                    <th>Blood Pressure</th>
                    <th>Temperature</th>
                  </tr>
                </thead>

                <tbody>
                  {vitals.map((vital, index) => (
                    <tr key={vital.id ?? vital.timestamp ?? index}>
                      <td>
                        {vital.recorded_at || vital.created_at || vital.timestamp
                          ? new Date(
                              vital.recorded_at || vital.created_at || vital.timestamp
                            ).toLocaleString()
                          : "—"}
                      </td>
                      <td>
                        {displayValue(
                          getVitalValue(vital, "heart_rate", "heartRate"),
                          " bpm"
                        )}
                      </td>
                      <td>
                        {displayValue(
                          getVitalValue(vital, "spo2", "oxygen_saturation"),
                          "%"
                        )}
                      </td>
                      <td>
                        {getVitalValue(
                          vital,
                          "systolic_bp",
                          "systolic"
                        ) != null
                          ? `${getVitalValue(
                              vital,
                              "systolic_bp",
                              "systolic"
                            )}/${getVitalValue(
                              vital,
                              "diastolic_bp",
                              "diastolic"
                            ) ?? "—"} mmHg`
                          : "Not available"}
                      </td>
                      <td>
                        {displayValue(
                          getVitalValue(
                            vital,
                            "temperature",
                            "body_temperature"
                          ),
                          " °C"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="app-footer">
          <p>HealthScan AI · Your health information in one place</p>
        </footer>
      </main>
    </div>
  );
}

export default App;

