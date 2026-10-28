
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";

const DEFAULT_API_BASE = import.meta.env.PROD
  ? "https://healthscan-ai-xabx.onrender.com"
  : "http://127.0.0.1:5000";
const API_BASE = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE).replace(/\/+$/, "");
const API = API_BASE.endsWith("/api") ? API_BASE : API_BASE + "/api";

async function apiRequest(path, options = {}) {
  const response = await fetch(API + path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.message || ("Request failed (" + response.status + ")"));
  }
  return data;
}

function normalizeVitals(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.vitals)) return data.vitals;
  if (Array.isArray(data?.readings)) return data.readings;
  return [];
}

function valueOf(item, ...keys) {
  for (const key of keys) {
    if (item?.[key] !== undefined && item[key] !== null && item[key] !== "") return item[key];
  }
  return null;
}

function formatDate(value, includeTime = false) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, includeTime
    ? { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
    : { day: "2-digit", month: "short", year: "numeric" });
}

function formatNumber(value, digits = 1) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Number(numeric.toFixed(digits)).toString() : "—";
}

function VitalChart({ title, data, unit, dataKey, color, description }) {
  const chartData = data.map((item, index) => ({
    ...item,
    chartLabel: formatDate(item.recorded_at || item.created_at || item.timestamp || item.date),
    chartId: item.id || index,
  }));
  const hasValues = chartData.some((item) => {
    const value = Number(item[dataKey]);
    return item[dataKey] !== null && item[dataKey] !== "" && Number.isFinite(value);
  });

  return (
    <article className="trend-chart-card">
      <div className="chart-title-row">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        <span className="chart-unit">{unit}</span>
      </div>
      {!hasValues ? (
        <p className="empty-state">No saved values for this measurement yet.</p>
      ) : (
        <div className="chart-canvas">
          <ResponsiveContainer width="100%" height={248}>
            <LineChart data={chartData} margin={{ top: 12, right: 12, bottom: 4, left: -12 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="#e5edf2" />
              <XAxis
                dataKey="chartLabel"
                tick={{ fontSize: 10, fill: "#708397" }}
                tickLine={false}
                axisLine={false}
                minTickGap={20}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#708397" }}
                tickLine={false}
                axisLine={false}
                width={44}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{ borderRadius: 12, borderColor: "#dce8ee", fontSize: 12 }}
                formatter={(value) => [String(value) + " " + unit, title]}
                labelFormatter={(label) => "Recorded: " + label}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                name={title}
                stroke={color}
                strokeWidth={2.8}
                dot={{ r: 3, fill: color, strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}

function getTrend(readings, keys) {
  const values = readings
    .map((item) => Number(valueOf(item, ...keys)))
    .filter((value) => Number.isFinite(value));
  if (values.length < 2) return { label: "Not enough data", tone: "neutral", delta: null, count: values.length };
  const first = values[0];
  const last = values[values.length - 1];
  const delta = last - first;
  const threshold = Math.max(Math.abs(first) * 0.025, 0.2);
  if (Math.abs(delta) < threshold) return { label: "Broadly stable", tone: "neutral", delta, count: values.length };
  return {
    label: delta > 0 ? "Trending upward" : "Trending downward",
    tone: delta > 0 ? "up" : "down",
    delta,
    count: values.length,
  };
}

const REFERENCE_GUIDE = [
  {
    title: "Resting heart rate",
    range: "Common adult reference: 60–100 bpm",
    body: "Resting heart rate can vary with age, fitness, medication, stress, fever, and other factors. Compare readings taken under similar resting conditions.",
    symbol: "♥",
  },
  {
    title: "Blood oxygen (SpO₂)",
    range: "Often around 95–100% at sea level",
    body: "Readings can be affected by cold fingers, movement, nail products, device quality, altitude, and some health conditions. A single reading is not a diagnosis.",
    symbol: "◉",
  },
  {
    title: "Blood pressure",
    range: "A commonly used optimal reference is below 120/80 mmHg",
    body: "Blood pressure categories depend on clinical guidance and repeated measurements. Cuff size, posture, stress, activity, and timing can change a result.",
    symbol: "＋",
  },
  {
    title: "Body temperature",
    range: "Often roughly 36.1–37.2 °C in adults",
    body: "Temperature varies with measurement method, time of day, age, and individual baseline. Follow the reference range and instructions provided by the lab or clinician.",
    symbol: "♨",
  },
];

function insightForLatest(label, value, unit, rangeText) {
  if (value === null || value === undefined || value === "") {
    return { title: label, value: "No reading yet", detail: "Add or extract a measurement to begin tracking.", tone: "neutral" };
  }
  return { title: label, value: String(value) + unit, detail: rangeText, tone: "neutral" };
}

function App() {
  const [vitals, setVitals] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reportsLoading, setReportsLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
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
  const [reportId, setReportId] = useState(null);
  const [extractedVitals, setExtractedVitals] = useState(null);
  const [analysis, setAnalysis] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [savingExtracted, setSavingExtracted] = useState(false);
  const [historyQuery, setHistoryQuery] = useState("");
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [compareLeft, setCompareLeft] = useState("");
  const [compareRight, setCompareRight] = useState("");
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);

  async function fetchVitals() {
    try {
      setLoading(true);
      const data = await apiRequest("/vitals", { signal: AbortSignal.timeout(12000) });
      setVitals(normalizeVitals(data));
    } catch (error) {
      setErrorMessage("Unable to load saved readings: " + (error.message || "check the backend and database."));
    } finally {
      setLoading(false);
    }
  }

  async function fetchReports() {
    try {
      setReportsLoading(true);
      const data = await apiRequest("/reports", { signal: AbortSignal.timeout(12000) });
      setReports(Array.isArray(data) ? data : Array.isArray(data?.reports) ? data.reports : []);
    } catch (error) {
      setErrorMessage((previous) => previous || ("Report history is unavailable: " + (error.message || "check the database.")));
      setReports([]);
    } finally {
      setReportsLoading(false);
    }
  }

  async function refreshAll() {
    setErrorMessage("");
    await Promise.all([fetchVitals(), fetchReports()]);
    setMessage("Dashboard data refreshed.");
  }

  useEffect(() => {
    fetchVitals();
    fetchReports();
  }, []);

  const latest = vitals.length ? vitals[vitals.length - 1] : null;
  const latestValues = {
    heart_rate: valueOf(latest, "heart_rate", "heartRate"),
    spo2: valueOf(latest, "spo2", "oxygen_saturation"),
    systolic_bp: valueOf(latest, "systolic_bp", "systolic"),
    diastolic_bp: valueOf(latest, "diastolic_bp", "diastolic"),
    temperature: valueOf(latest, "temperature", "body_temperature"),
  };

  const summaryCards = [
    { title: "Heart rate", value: latestValues.heart_rate, unit: " bpm", icon: "♥", helper: "Latest saved reading" },
    { title: "Blood oxygen", value: latestValues.spo2, unit: "%", icon: "◉", helper: "Latest saved reading" },
    {
      title: "Blood pressure",
      value: latestValues.systolic_bp != null && latestValues.diastolic_bp != null
        ? latestValues.systolic_bp + "/" + latestValues.diastolic_bp
        : null,
      unit: " mmHg",
      icon: "＋",
      helper: "Latest saved reading",
    },
    { title: "Temperature", value: latestValues.temperature, unit: " °C", icon: "♨", helper: "Latest saved reading" },
  ];

  const trendCards = [
    { title: "Heart rate", ...getTrend(vitals, ["heart_rate", "heartRate"]), unit: "bpm" },
    { title: "SpO₂", ...getTrend(vitals, ["spo2", "oxygen_saturation"]), unit: "%" },
    { title: "Systolic BP", ...getTrend(vitals, ["systolic_bp", "systolic"]), unit: "mmHg" },
    { title: "Temperature", ...getTrend(vitals, ["temperature", "body_temperature"]), unit: "°C" },
  ];

  const historyFiltered = useMemo(() => {
    const query = historyQuery.trim().toLowerCase();
    return reports.filter((item) => {
      if (!query) return true;
      return String(item.filename || "").toLowerCase().includes(query)
        || String(item.report_text || "").toLowerCase().includes(query)
        || String(item.ai_analysis || "").toLowerCase().includes(query);
    });
  }, [reports, historyQuery]);

  const extractedPressure = extractedVitals && (extractedVitals.systolic_bp != null || extractedVitals.diastolic_bp != null)
    ? String(extractedVitals.systolic_bp ?? "—") + "/" + String(extractedVitals.diastolic_bp ?? "—")
    : null;
  const extractedItems = extractedVitals ? [
    { key: "heart_rate", label: "Heart rate", value: extractedVitals.heart_rate, unit: "bpm" },
    { key: "spo2", label: "Blood oxygen", value: extractedVitals.spo2, unit: "%" },
    { key: "blood_pressure", label: "Blood pressure", value: extractedPressure, unit: extractedPressure ? "mmHg" : "" },
    { key: "temperature", label: "Temperature", value: extractedVitals.temperature, unit: "°C" },
  ] : [];
  const extractedCount = extractedItems.filter((item) => item.value !== null && item.value !== undefined && item.value !== "").length;

  function handleFormChange(event) {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  }

  async function handleSaveVitals(event) {
    event.preventDefault();
    setMessage("");
    setErrorMessage("");
    const payload = {};
    Object.entries(form).forEach(([key, value]) => {
      if (value !== "") payload[key] = Number(value);
    });
    if (!Object.keys(payload).length) {
      setErrorMessage("Enter at least one measurement before saving.");
      return;
    }
    if (payload.spo2 != null && (payload.spo2 < 1 || payload.spo2 > 100)) {
      setErrorMessage("SpO₂ must be between 1 and 100.");
      return;
    }
    if (payload.heart_rate != null && (payload.heart_rate < 1 || payload.heart_rate > 300)) {
      setErrorMessage("Heart rate must be between 1 and 300 bpm.");
      return;
    }
    if (payload.systolic_bp != null && (payload.systolic_bp < 1 || payload.systolic_bp > 300)) {
      setErrorMessage("Systolic blood pressure must be between 1 and 300 mmHg.");
      return;
    }
    if (payload.diastolic_bp != null && (payload.diastolic_bp < 1 || payload.diastolic_bp > 200)) {
      setErrorMessage("Diastolic blood pressure must be between 1 and 200 mmHg.");
      return;
    }
    if (payload.temperature != null && (payload.temperature < 25 || payload.temperature > 45)) {
      setErrorMessage("Temperature must be between 25 and 45 °C.");
      return;
    }
    try {
      setSaving(true);
      await apiRequest("/vitals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMessage("Vitals saved to your history.");
      setForm({ heart_rate: "", spo2: "", systolic_bp: "", diastolic_bp: "", temperature: "" });
      await fetchVitals();
    } catch (error) {
      setErrorMessage(error.message || "Could not save readings.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUploadReport(event) {
    event.preventDefault();
    if (!report) {
      setErrorMessage("Choose a PDF report first.");
      return;
    }
    if (report.size > 15 * 1024 * 1024) {
      setErrorMessage("The selected PDF is larger than the 15 MB upload limit.");
      return;
    }
    try {
      setUploading(true);
      setMessage("");
      setErrorMessage("");
      setReportText("");
      setExtractedVitals(null);
      setAnalysis("");
      setAnalysisError("");
      setReportId(null);
      const data = await apiRequest("/upload-report", {
        method: "POST",
        body: (() => {
          const body = new FormData();
          body.append("file", report);
          return body;
        })(),
        signal: AbortSignal.timeout(30000),
      });
      setReportId(data.report_id ?? data.id ?? null);
      setReportText(data.text ?? data.extracted_text ?? "");
      setMessage(data.message || "PDF text extracted.");
      await fetchReports();
    } catch (error) {
      setErrorMessage(error.message || "Could not read the selected PDF.");
    } finally {
      setUploading(false);
    }
  }

  async function handleExtractVitals() {
    if (!reportText.trim()) {
      setErrorMessage("Upload a text-based PDF or load a report from history first.");
      return;
    }
    try {
      setExtracting(true);
      setMessage("");
      setErrorMessage("");
      const data = await apiRequest("/extract-vitals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: reportText }),
        signal: AbortSignal.timeout(15000),
      });
      setExtractedVitals(data.vitals ?? data.extracted_vitals ?? data);
      setMessage((data.found_count ?? 0) + " supported measurement(s) detected. Please verify each value against the source report.");
    } catch (error) {
      setErrorMessage(error.message || "Vital extraction failed.");
    } finally {
      setExtracting(false);
    }
  }

  async function handleAnalyzeReport() {
    if (!reportText.trim()) {
      setAnalysisError("Upload a text-based PDF or load a report from history before requesting an explanation.");
      return;
    }
    try {
      setAnalyzing(true);
      setAnalysis("");
      setAnalysisError("");
      setMessage("Generating a plain-language explanation. This can take up to a minute.");
      const data = await apiRequest("/analyze-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(95000),
        body: JSON.stringify({ text: reportText, report_id: reportId }),
      });
      const result = typeof data.analysis === "string" ? data.analysis.trim() : "";
      if (!result) throw new Error(data.message || "The AI service returned an empty explanation.");
      setAnalysis(result);
      setMessage(data.message || "Explanation generated.");
      await fetchReports();
    } catch (error) {
      const detail = error?.name === "TimeoutError"
        ? "The AI request exceeded 95 seconds. Check Render logs and retry."
        : (error.message || "Could not generate the AI explanation.");
      setAnalysisError(detail);
      setErrorMessage("AI explanation could not be generated.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleSaveExtracted() {
    if (!extractedVitals || extractedCount === 0) {
      setErrorMessage("There are no detected measurements to save.");
      return;
    }
    const payload = {
      heart_rate: extractedVitals.heart_rate ?? null,
      spo2: extractedVitals.spo2 ?? null,
      systolic_bp: extractedVitals.systolic_bp ?? null,
      diastolic_bp: extractedVitals.diastolic_bp ?? null,
      temperature: extractedVitals.temperature ?? null,
    };
    try {
      setSavingExtracted(true);
      await apiRequest("/vitals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMessage("Extracted measurements saved. Check the date and values before using them.");
      await fetchVitals();
    } catch (error) {
      setErrorMessage(error.message || "Could not save extracted measurements.");
    } finally {
      setSavingExtracted(false);
    }
  }

  function loadReport(item) {
    setSelectedHistoryId(item.id);
    setReportId(item.id);
    setReportText(item.report_text || "");
    setAnalysis(item.ai_analysis || "");
    setExtractedVitals(null);
    setAnalysisError("");
    setMessage("Loaded " + (item.filename || "saved report") + ". You can extract values or regenerate the explanation.");
    document.getElementById("report-lab")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleCompareReports() {
    if (!compareLeft || !compareRight || compareLeft === compareRight) {
      setErrorMessage("Choose two different saved reports to compare.");
      return;
    }
    const left = reports.find((item) => String(item.id) === String(compareLeft));
    const right = reports.find((item) => String(item.id) === String(compareRight));
    if (!left || !right) {
      setErrorMessage("One of the selected reports is no longer available.");
      return;
    }
    try {
      setComparing(true);
      setErrorMessage("");
      const [leftResult, rightResult] = await Promise.all([
        apiRequest("/extract-vitals", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: left.report_text || "" }),
        }),
        apiRequest("/extract-vitals", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: right.report_text || "" }),
        }),
      ]);
      setComparison({
        left: { title: left.filename || "Report A", date: left.uploaded_at, vitals: leftResult.vitals || {} },
        right: { title: right.filename || "Report B", date: right.uploaded_at, vitals: rightResult.vitals || {} },
      });
      setMessage("Comparison generated from the two saved report texts. Verify extracted values against each original document.");
    } catch (error) {
      setErrorMessage(error.message || "Could not compare the selected reports.");
    } finally {
      setComparing(false);
    }
  }

  function exportVitalsCsv() {
    const columns = [
      ["recorded_at", "Recorded at"],
      ["heart_rate", "Heart rate (bpm)"],
      ["spo2", "SpO2 (%)"],
      ["systolic_bp", "Systolic BP (mmHg)"],
      ["diastolic_bp", "Diastolic BP (mmHg)"],
      ["temperature", "Temperature (C)"],
    ];
    const escapeCsv = (value) => '"' + String(value ?? "").replace(/"/g, '""') + '"';
    const rows = [columns.map((column) => escapeCsv(column[1])).join(",")];
    vitals.forEach((item) => rows.push(columns.map((column) => escapeCsv(item[column[0]])).join(",")));
    const blob = new Blob(["\uFEFF" + rows.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "healthscan-vitals-history.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setMessage("CSV export prepared from saved readings.");
  }

  function printSummary() {
    window.print();
  }

  const readingCount = vitals.length;
  const reportCount = reports.length;
  const latestDate = latest ? formatDate(latest.recorded_at || latest.created_at || latest.timestamp, true) : "No saved readings yet";
  const insightCards = [
    insightForLatest("Heart rate", latestValues.heart_rate, " bpm", "General guide: 60–100 bpm at rest for many adults"),
    insightForLatest("SpO₂", latestValues.spo2, "%", "General guide: often 95–100% at sea level"),
    insightForLatest(
      "Blood pressure",
      latestValues.systolic_bp != null && latestValues.diastolic_bp != null ? latestValues.systolic_bp + "/" + latestValues.diastolic_bp : null,
      " mmHg",
      "Interpret using clinician guidance and repeated measurements",
    ),
    insightForLatest("Temperature", latestValues.temperature, " °C", "Typical adult range varies by method and individual"),
  ];

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-symbol" aria-hidden="true">✚</div>
          <div className="brand-copy">
            <p className="brand-kicker">PERSONAL HEALTH INTELLIGENCE</p>
            <h1>HealthScan <span>AI</span></h1>
            <p className="brand-subtitle">Understand reports. Track readings. Explore trends.</p>
          </div>
        </div>
        <div className="header-actions">
          <span className="dashboard-status"><i aria-hidden="true" /> Live dashboard</span>
          <button className="refresh-button" type="button" onClick={refreshAll}><span aria-hidden="true">↻</span> Refresh</button>
        </div>
      </header>

      <main className="dashboard">
        <section className="welcome-section">
          <div className="welcome-copy">
            <p className="section-eyebrow">YOUR HEALTH WORKSPACE</p>
            <h2>Clarity from your health data.</h2>
            <p>Bring report text, vital measurements, longitudinal trends, and AI-assisted explanations into one place. Every extracted value remains reviewable against its source.</p>
            <div className="hero-actions">
              <a className="hero-link primary-link" href="#report-lab">Analyze a report <span aria-hidden="true">↗</span></a>
              <a className="hero-link" href="#vitals-entry">Add a measurement <span aria-hidden="true">↓</span></a>
            </div>
          </div>
          <div className="welcome-illustration" aria-hidden="true">
            <span className="pulse-orbit orbit-one" />
            <span className="pulse-orbit orbit-two" />
            <span className="pulse-cross">✚</span>
            <span className="pulse-line">⌁</span>
          </div>
        </section>

        {errorMessage && (
          <div className="feedback-message feedback-error" role="alert">
            <span>{errorMessage}</span>
            <button type="button" onClick={() => setErrorMessage("")} aria-label="Dismiss error">×</button>
          </div>
        )}
        {message && (
          <div className="feedback-message" role="status">
            <span>{message}</span>
            <button type="button" onClick={() => setMessage("")} aria-label="Dismiss message">×</button>
          </div>
        )}

        <section className="overview-strip" aria-label="Project overview">
          <div className="overview-stat"><span className="overview-icon">◷</span><div><strong>{loading ? "…" : readingCount}</strong><span>Saved readings</span></div></div>
          <div className="overview-stat"><span className="overview-icon">▤</span><div><strong>{reportsLoading ? "…" : reportCount}</strong><span>Saved reports</span></div></div>
          <div className="overview-stat"><span className="overview-icon">⌁</span><div><strong>{vitals.length >= 2 ? "Active" : "Getting started"}</strong><span>Trend tracking</span></div></div>
          <div className="overview-stat"><span className="overview-icon">✧</span><div><strong>PDF + AI</strong><span>Report workflow</span></div></div>
        </section>

        <section className="section" id="overview">
          <div className="section-heading">
            <div><p className="section-eyebrow">AT A GLANCE</p><h2>Latest measurements</h2><p>Most recent values saved in the database. These cards do not use demo values.</p></div>
            <span className="reading-count">{loading ? "Loading…" : readingCount + " readings"}</span>
          </div>
          <div className="vitals-grid">
            {summaryCards.map((card) => (
              <article className="vital-card" key={card.title}>
                <div className="vital-card-top"><span className="vital-icon">{card.icon}</span><span className="vital-label">{card.title}</span></div>
                <h3>{card.value === null || card.value === undefined ? "—" : String(card.value) + card.unit}</h3>
                <p className="metric-helper">{card.helper}</p>
              </article>
            ))}
          </div>
          {!loading && !vitals.length && <p className="empty-state">Your saved history is empty. Add a reading below or extract supported measurements from a report.</p>}
          {latest && <p className="last-updated">Latest saved record: {latestDate}</p>}
        </section>

        <section className="section" id="trends">
          <div className="section-heading section-heading-wrap">
            <div><p className="section-eyebrow">LONGITUDINAL VIEW</p><h2>Vitals trends</h2><p>Charts are generated from real saved readings only; no synthetic readings are mixed into your history.</p></div>
            <button className="secondary-action" type="button" onClick={exportVitalsCsv} disabled={!vitals.length}>Export CSV ↓</button>
          </div>
          {vitals.length < 2 && (
            <div className="info-banner">
              <strong>{vitals.length === 0 ? "Waiting for your first reading" : "One reading saved so far"}</strong>
              <span>{vitals.length === 0 ? "Once you save measurements on different dates, trends will appear here." : "Save another reading on a later date to start seeing changes over time."}</span>
            </div>
          )}
          <div className="trend-chart-grid">
            <VitalChart title="Heart rate" data={vitals} unit="bpm" dataKey="heart_rate" color="#d95a67" description="Beats per minute" />
            <VitalChart title="Blood oxygen (SpO₂)" data={vitals} unit="%" dataKey="spo2" color="#2c87c9" description="Oxygen saturation" />
            <VitalChart title="Systolic blood pressure" data={vitals} unit="mmHg" dataKey="systolic_bp" color="#7b61c9" description="Upper blood pressure value" />
            <VitalChart title="Body temperature" data={vitals} unit="°C" dataKey="temperature" color="#dd9638" description="Stored in Celsius" />
          </div>
        </section>

        <section className="section" id="insights">
          <div className="section-heading">
            <div><p className="section-eyebrow">EXPLAINABLE ANALYTICS</p><h2>Trend & measurement insights</h2><p>Simple, transparent summaries calculated from your saved history—not a diagnosis or a substitute for clinical review.</p></div>
          </div>
          <div className="insight-grid">
            {trendCards.map((item) => (
              <article className="insight-card" key={item.title}>
                <div className="insight-card-head"><strong>{item.title}</strong><span className={"trend-tag trend-" + item.tone}>{item.label}</span></div>
                <div className="insight-number">
                  {item.delta === null ? "—" : (item.delta > 0 ? "+" : "") + formatNumber(item.delta, 1) + " " + item.unit}
                </div>
                <p>{item.count < 2 ? "At least two saved numeric readings are needed to calculate a change." : "Difference between the first and latest available values in the saved history."}</p>
              </article>
            ))}
          </div>
          <div className="insight-disclaimer"><strong>How to read this:</strong> A rising or falling line is a pattern in the recorded values, not evidence by itself that a condition is improving or worsening. Missing values are skipped; readings taken under different conditions may not be directly comparable.</div>
          <h3 className="subsection-title">Latest reading guide</h3>
          <div className="insight-grid">
            {insightCards.map((item) => (
              <article className="latest-guide-card" key={item.title}>
                <span>{item.title}</span><strong>{item.value}</strong><p>{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section" id="vitals-entry">
          <div className="section-heading">
            <div><p className="section-eyebrow">MANUAL TRACKING</p><h2>Add a measurement</h2><p>Enter only values that you have actually measured. You can save one or several fields at a time.</p></div>
          </div>
          <form className="vitals-form" onSubmit={handleSaveVitals}>
            <label>Heart rate (bpm)<input type="number" name="heart_rate" min="1" max="300" value={form.heart_rate} onChange={handleFormChange} placeholder="e.g. 72" /></label>
            <label>Blood oxygen (%)<input type="number" name="spo2" min="1" max="100" value={form.spo2} onChange={handleFormChange} placeholder="e.g. 98" /></label>
            <label>Systolic BP (mmHg)<input type="number" name="systolic_bp" min="1" max="300" value={form.systolic_bp} onChange={handleFormChange} placeholder="e.g. 120" /></label>
            <label>Diastolic BP (mmHg)<input type="number" name="diastolic_bp" min="1" max="200" value={form.diastolic_bp} onChange={handleFormChange} placeholder="e.g. 80" /></label>
            <label>Temperature (°C)<input type="number" name="temperature" step="0.1" min="25" max="45" value={form.temperature} onChange={handleFormChange} placeholder="e.g. 36.8" /></label>
            <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save measurements"}</button>
          </form>
          <p className="form-note">Basic input bounds catch obvious entry mistakes. They do not determine whether a measurement is medically safe.</p>
        </section>

        <section className="section" id="report-lab">
          <div className="section-heading">
            <div><p className="section-eyebrow">PDF + AI WORKFLOW</p><h2>Medical report lab</h2><p>Upload a PDF, inspect extracted text, detect supported vitals, and request a separate plain-language explanation.</p></div>
            <span className="result-count">Up to 15 MB · PDF</span>
          </div>
          <div className="report-lab-grid">
            <div className="report-upload-panel">
              <form className="report-form" onSubmit={handleUploadReport}>
                <label className="file-label">Select medical report (PDF)
                  <input type="file" accept=".pdf,application/pdf" onChange={(event) => {
                    setReport(event.target.files?.[0] ?? null);
                    setReportText("");
                    setReportId(null);
                    setExtractedVitals(null);
                    setAnalysis("");
                    setAnalysisError("");
                    setSelectedHistoryId(null);
                  }} />
                </label>
                {report && <p className="selected-file">Selected: {report.name} · {(report.size / (1024 * 1024)).toFixed(2)} MB</p>}
                <button className="primary-button" type="submit" disabled={uploading || !report}>{uploading ? "Reading PDF…" : "1. Upload & extract text"}</button>
              </form>
              <div className="report-actions">
                <button type="button" onClick={handleExtractVitals} disabled={extracting || !reportText.trim()}>{extracting ? "Finding values…" : "2. Extract vitals"}</button>
                <button type="button" onClick={handleAnalyzeReport} disabled={analyzing || !reportText.trim()}>{analyzing ? "Generating explanation…" : "3. Explain with AI"}</button>
              </div>
              <div className="workflow-note"><span className="workflow-number">A</span><p><strong>Structured extraction</strong><br />Finds supported numbers near vital labels. Always verify each value against the PDF.</p></div>
              <div className="workflow-note"><span className="workflow-number">B</span><p><strong>AI explanation</strong><br />Uses Gemini to explain the text in plain language; the generated content may be wrong or incomplete.</p></div>
            </div>
            <div className="report-text-panel">
              <div className="panel-title-row"><div><h3>Extracted source text</h3><p>Review the original text sent to the extraction and explanation steps.</p></div><span className="panel-pill">{reportText ? reportText.length.toLocaleString() + " characters" : "No text yet"}</span></div>
              {reportText ? <pre className="report-source-text">{reportText}</pre> : <div className="empty-report-text"><span>▤</span><strong>Your report text appears here</strong><p>Text-based PDFs work best. Image-only scans currently need OCR, which is not enabled in this version.</p></div>}
            </div>
          </div>

          {extractedVitals && (
            <div className="results-panel">
              <div className="panel-title-row"><div><p className="section-eyebrow">RESULT 01</p><h3>Detected measurements</h3><p>{extractedCount} supported measurement group(s) found in the uploaded text.</p></div><span className="result-count">Review before saving</span></div>
              <div className="extracted-vitals-grid">
                {extractedItems.map((item) => (
                  <div className="extracted-vital" key={item.key}><span>{item.label}</span><strong>{item.value == null || item.value === "" ? "Not detected" : String(item.value) + (item.unit ? " " + item.unit : "")}</strong></div>
                ))}
              </div>
              <div className="result-footer"><p>Extraction is pattern-based and can miss alternate layouts or select a nearby number. Compare every value with the PDF before saving it.</p><button type="button" className="primary-button" onClick={handleSaveExtracted} disabled={savingExtracted || !extractedCount}>{savingExtracted ? "Saving…" : "Save detected values to history"}</button></div>
            </div>
          )}

          {(analysisError || analysis) && (
            <div className="results-panel analysis-panel">
              <div className="panel-title-row"><div><p className="section-eyebrow">RESULT 02</p><h3>AI-assisted explanation</h3><p>Educational information only. Not a diagnosis or treatment plan.</p></div><span className="ai-badge">✧ Gemini</span></div>
              {analysisError ? <div className="ai-error" role="alert">{analysisError}</div> : (
                <>
                  <div className="analysis-content">{analysis.split(/\n{2,}/).map((paragraph, index) => {
                    const clean = paragraph.trim();
                    if (!clean) return null;
                    const isHeading = clean.length < 90 && (/^(#{1,6}\s|[0-9]+[.)]\s|Report Summary|Important Values|Values Outside|Simple Explanation|Questions to Ask)/i.test(clean));
                    return isHeading
                      ? <h4 key={index}>{clean.replace(/^#{1,6}\s*/, "").replace(/^\d+[.)]\s*/, "")}</h4>
                      : <p key={index}>{clean.replace(/\*\*/g, "")}</p>;
                  })}</div>
                  <div className="ai-safety-note">AI can misunderstand clinical context or miss important details. Use the source report and consult a qualified healthcare professional for decisions.</div>
                </>
              )}
            </div>
          )}
        </section>

        <section className="section" id="report-history">
          <div className="section-heading section-heading-wrap">
            <div><p className="section-eyebrow">REPORT VAULT</p><h2>Saved report history</h2><p>Search previously uploaded report text and explanations, then reload a report into the analysis workspace.</p></div>
            <span className="reading-count">{reportsLoading ? "Loading…" : reportCount + " saved"}</span>
          </div>
          <div className="history-search-row">
            <label className="history-search">Search report history<input type="search" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Search by filename or report wording…" /></label>
            <button type="button" className="secondary-action" onClick={fetchReports} disabled={reportsLoading}>{reportsLoading ? "Loading…" : "Refresh history"}</button>
          </div>
          {reportsLoading ? <p className="empty-state">Loading saved report history…</p> : historyFiltered.length === 0 ? (
            <div className="empty-history"><span>▤</span><strong>{reportCount ? "No reports match this search" : "No saved reports yet"}</strong><p>Upload a text-based PDF above. Reports are listed here when the database save succeeds.</p></div>
          ) : (
            <div className="report-history-list">
              {historyFiltered.map((item) => (
                <article className={"report-history-item" + (String(selectedHistoryId) === String(item.id) ? " is-selected" : "")} key={item.id}>
                  <div className="report-history-icon">PDF</div>
                  <div className="report-history-copy"><strong>{item.filename || "Medical report"}</strong><span>{formatDate(item.uploaded_at, true)} · {String(item.report_text || "").length.toLocaleString()} characters</span><p>{item.ai_analysis ? "AI explanation saved" : "No saved AI explanation"} · Report ID {item.id}</p></div>
                  <button type="button" className="secondary-action" onClick={() => loadReport(item)}>{String(selectedHistoryId) === String(item.id) ? "Loaded ✓" : "Open report"}</button>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="section" id="compare-reports">
          <div className="section-heading">
            <div><p className="section-eyebrow">LONGITUDINAL REPORT REVIEW</p><h2>Compare two reports</h2><p>Run the same vital extractor on two saved reports side by side. This is an exploratory comparison, not a clinical interpretation.</p></div>
          </div>
          <div className="compare-controls">
            <label>Earlier / first report<select value={compareLeft} onChange={(event) => { setCompareLeft(event.target.value); setComparison(null); }}><option value="">Choose a report…</option>{reports.map((item) => <option key={item.id} value={item.id}>{item.filename || "Report"} · {formatDate(item.uploaded_at)}</option>)}</select></label>
            <div className="compare-arrow" aria-hidden="true">→</div>
            <label>Later / second report<select value={compareRight} onChange={(event) => { setCompareRight(event.target.value); setComparison(null); }}><option value="">Choose a report…</option>{reports.map((item) => <option key={item.id} value={item.id}>{item.filename || "Report"} · {formatDate(item.uploaded_at)}</option>)}</select></label>
            <button type="button" className="primary-button" onClick={handleCompareReports} disabled={comparing || reports.length < 2}>{comparing ? "Comparing…" : "Compare reports"}</button>
          </div>
          {comparison && (
            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead><tr><th>Measurement</th><th>{comparison.left.title}<small>{formatDate(comparison.left.date)}</small></th><th>{comparison.right.title}<small>{formatDate(comparison.right.date)}</small></th><th>Difference</th></tr></thead>
                <tbody>
                  {[
                    { label: "Heart rate", key: "heart_rate", unit: " bpm" },
                    { label: "SpO₂", key: "spo2", unit: "%" },
                    { label: "Systolic BP", key: "systolic_bp", unit: " mmHg" },
                    { label: "Diastolic BP", key: "diastolic_bp", unit: " mmHg" },
                    { label: "Temperature", key: "temperature", unit: " °C" },
                  ].map((row) => {
                    const left = comparison.left.vitals[row.key];
                    const right = comparison.right.vitals[row.key];
                    const delta = left != null && right != null && Number.isFinite(Number(left)) && Number.isFinite(Number(right))
                      ? Number(right) - Number(left) : null;
                    return <tr key={row.key}><th>{row.label}</th><td>{left == null ? "Not detected" : String(left) + row.unit}</td><td>{right == null ? "Not detected" : String(right) + row.unit}</td><td>{delta == null ? "—" : (delta > 0 ? "+" : "") + formatNumber(delta, 2) + row.unit}</td></tr>;
                  })}
                </tbody>
              </table>
              <p className="comparison-note">Differences may reflect extraction errors, different measurement conditions, or report layout changes. Confirm both values against their original PDFs; the difference does not establish a clinical trend by itself.</p>
            </div>
          )}
        </section>

        <section className="section" id="health-guide">
          <div className="section-heading">
            <div><p className="section-eyebrow">HEALTH LITERACY LIBRARY</p><h2>Know your measurements</h2><p>A concise reference guide to the vital signs supported by this project.</p></div>
            <button type="button" className="secondary-action" onClick={printSummary}>Print / save page ⤓</button>
          </div>
          <div className="reference-grid">
            {REFERENCE_GUIDE.map((item) => (
              <article className="reference-card" key={item.title}>
                <span className="reference-symbol">{item.symbol}</span><h3>{item.title}</h3><strong>{item.range}</strong><p>{item.body}</p>
              </article>
            ))}
          </div>
          <div className="medical-disclaimer"><strong>Important:</strong> These are broad educational reference points for adults, not personal targets. Reference values vary by age, pregnancy, altitude, symptoms, existing conditions, measurement device, and clinical guidance. Do not change medication or treatment based on this dashboard.</div>
        </section>

        <section className="section project-method">
          <div><p className="section-eyebrow">PROJECT METHOD</p><h2>How HealthScan AI works</h2><p>A transparent multi-stage pipeline keeps numeric extraction separate from natural-language explanation.</p></div>
          <div className="method-steps">
            <div><span>01</span><strong>PDF ingestion</strong><p>PyPDF extracts selectable text from a user-provided PDF.</p></div>
            <div><span>02</span><strong>Vital extraction</strong><p>Regex-based rules detect supported labels and associated numeric values.</p></div>
            <div><span>03</span><strong>AI explanation</strong><p>Gemini generates a plain-language explanation with explicit uncertainty.</p></div>
            <div><span>04</span><strong>History & analytics</strong><p>MySQL stores supported records; React visualizes trends and compares report extracts.</p></div>
          </div>
        </section>

        <footer className="app-footer">
          <div><strong>HealthScan AI</strong><p>Academic minor project · PDF processing · Full-stack development · AI-assisted explanation</p></div>
          <div className="footer-right"><span>Built for learning and informational use</span><span>Not a diagnostic medical device</span></div>
        </footer>
      </main>
    </div>
  );
}

export default App;
