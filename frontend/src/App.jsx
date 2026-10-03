import { useEffect, useState } from "react";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import "./App.css";


function App() {

  // -----------------------------
  // VITALS
  // -----------------------------

  const [vitals, setVitals] = useState([]);

  const [formData, setFormData] = useState({
    heart_rate: "",
    spo2: "",
    systolic_bp: "",
    diastolic_bp: "",
    temperature: "",
  });


  // -----------------------------
  // REPORT
  // -----------------------------

  const [selectedFile, setSelectedFile] = useState(null);

  const [reportText, setReportText] = useState("");

  const [analysis, setAnalysis] = useState("");

  const [analyzing, setAnalyzing] = useState(false);


  // -----------------------------
  // EXTRACTED VITALS
  // -----------------------------

  const [extractedVitals, setExtractedVitals] = useState(null);

  const [extractingVitals, setExtractingVitals] = useState(false);


  // -----------------------------
  // GET VITALS
  // -----------------------------

  const fetchVitals = () => {

    fetch("http://127.0.0.1:5000/api/vitals")

      .then((response) => response.json())

      .then((data) => {

        setVitals(data);

      })

      .catch((error) => {

        console.error("Error loading vitals:", error);

      });

  };


  useEffect(() => {

    fetchVitals();

  }, []);


  // -----------------------------
  // FORM INPUT
  // -----------------------------

  const handleChange = (event) => {

    setFormData({
      ...formData,
      [event.target.name]: event.target.value,
    });

  };


  // -----------------------------
  // SAVE MANUAL VITALS
  // -----------------------------

  const handleSubmit = (event) => {

    event.preventDefault();

    fetch("http://127.0.0.1:5000/api/vitals", {

      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({

        heart_rate: Number(formData.heart_rate),

        spo2: Number(formData.spo2),

        systolic_bp: Number(formData.systolic_bp),

        diastolic_bp: Number(formData.diastolic_bp),

        temperature: Number(formData.temperature),

      }),

    })

      .then((response) => response.json())

      .then((data) => {

        alert(data.message);

        setFormData({
          heart_rate: "",
          spo2: "",
          systolic_bp: "",
          diastolic_bp: "",
          temperature: "",
        });

        fetchVitals();

      })

      .catch((error) => {

        console.error("Error saving vitals:", error);

        alert("Could not save vitals.");

      });

  };


  // -----------------------------
  // FILE SELECT
  // -----------------------------

  const handleFileChange = (event) => {

    const file = event.target.files[0];

    setSelectedFile(file);

    // Reset previous report information
    setReportText("");

    setExtractedVitals(null);

    setAnalysis("");

  };


  // -----------------------------
  // UPLOAD REPORT
  // -----------------------------

  const handleUpload = () => {

    if (!selectedFile) {

      alert("Please select a PDF first.");

      return;

    }


    const formData = new FormData();

    formData.append("file", selectedFile);


    fetch("http://127.0.0.1:5000/api/upload-report", {

      method: "POST",

      body: formData,

    })

      .then((response) => response.json())

      .then((data) => {

        alert(data.message);

        setReportText(data.text);

      })

      .catch((error) => {

        console.error("Error uploading report:", error);

        alert("Could not upload report.");

      });

  };


  // -----------------------------
  // EXTRACT VITALS FROM REPORT
  // -----------------------------

  const handleExtractVitals = () => {

    if (!reportText) {

      alert("Please upload a report first.");

      return;

    }


    setExtractingVitals(true);


    fetch("http://127.0.0.1:5000/api/extract-vitals", {

      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        text: reportText,
      }),

    })

      .then((response) => response.json())

      .then((data) => {

        if (data.vitals) {

          setExtractedVitals(data.vitals);

        } else {

          alert(
            data.message || "Could not extract vitals."
          );

        }

      })

      .catch((error) => {

        console.error(
          "Error extracting vitals:",
          error
        );

        alert("Could not extract vitals.");

      })

      .finally(() => {

        setExtractingVitals(false);

      });

  };


  // -----------------------------
  // SAVE EXTRACTED VITALS
  // -----------------------------

  const handleSaveExtractedVitals = () => {

    if (!extractedVitals) {

      alert("No extracted vitals available.");

      return;

    }


    if (

      extractedVitals.heart_rate === null ||

      extractedVitals.spo2 === null ||

      extractedVitals.systolic_bp === null ||

      extractedVitals.diastolic_bp === null ||

      extractedVitals.temperature === null

    ) {

      alert(
        "Some vital values are missing from the report. They cannot be saved as a complete vital record."
      );

      return;

    }


    fetch("http://127.0.0.1:5000/api/vitals", {

      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({

        heart_rate: extractedVitals.heart_rate,

        spo2: extractedVitals.spo2,

        systolic_bp:
          extractedVitals.systolic_bp,

        diastolic_bp:
          extractedVitals.diastolic_bp,

        temperature:
          extractedVitals.temperature,

      }),

    })

      .then((response) => response.json())

      .then((data) => {

        alert(data.message);

        fetchVitals();

      })

      .catch((error) => {

        console.error(
          "Error saving extracted vitals:",
          error
        );

        alert(
          "Could not save extracted vitals."
        );

      });

  };


  // -----------------------------
  // ANALYZE REPORT WITH GEMINI
  // -----------------------------

  const handleAnalyze = () => {

    if (!reportText) {

      alert("Please upload a report first.");

      return;

    }


    setAnalyzing(true);


    fetch(
      "http://127.0.0.1:5000/api/analyze-report",
      {

        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          text: reportText,
        }),

      }
    )

      .then((response) => response.json())

      .then((data) => {

        if (data.analysis) {

          setAnalysis(data.analysis);

        } else {

          alert(
            data.message ||
              "Could not analyze report."
          );

        }

      })

      .catch((error) => {

        console.error(
          "Error analyzing report:",
          error
        );

        alert("Could not analyze report.");

      })

      .finally(() => {

        setAnalyzing(false);

      });

  };


  return (

    <div className="app">


      {/* HEADER */}

      <header className="app-header">

        <h1>
          ❤️ HealthScan AI
        </h1>

        <p>
          Health Report & Vital Analysis Platform
        </p>

      </header>



      <main className="container">


        {/* MANUAL VITALS */}

        <section className="report-section">

          <h2>
            ❤️ Enter Health Vitals
          </h2>

          <p>
            Enter your health measurements
            manually.
          </p>


          <form
            onSubmit={handleSubmit}
            className="vitals-form"
          >

            <div className="vitals-grid">


              <div>

                <label>
                  Heart Rate (BPM)
                </label>

                <input
                  type="number"
                  name="heart_rate"
                  value={formData.heart_rate}
                  onChange={handleChange}
                  required
                />

              </div>


              <div>

                <label>
                  SpO₂ (%)
                </label>

                <input
                  type="number"
                  name="spo2"
                  value={formData.spo2}
                  onChange={handleChange}
                  required
                />

              </div>


              <div>

                <label>
                  Systolic BP
                </label>

                <input
                  type="number"
                  name="systolic_bp"
                  value={formData.systolic_bp}
                  onChange={handleChange}
                  required
                />

              </div>


              <div>

                <label>
                  Diastolic BP
                </label>

                <input
                  type="number"
                  name="diastolic_bp"
                  value={formData.diastolic_bp}
                  onChange={handleChange}
                  required
                />

              </div>


              <div>

                <label>
                  Temperature (°C)
                </label>

                <input
                  type="number"
                  step="0.1"
                  name="temperature"
                  value={formData.temperature}
                  onChange={handleChange}
                  required
                />

              </div>


            </div>


            <button
              type="submit"
              className="upload-button"
            >
              Save Vitals
            </button>


          </form>

        </section>



        {/* HEART RATE */}

        <section className="report-section">

          <h2>
            ❤️ Heart Rate Trend
          </h2>


          {vitals.length > 0 ? (

            <ResponsiveContainer
              width="100%"
              height={300}
            >

              <LineChart
                data={[...vitals].reverse()}
              >

                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis
                  dataKey="recorded_at"
                />

                <YAxis />

                <Tooltip />

                <Legend />

                <Line
                  type="monotone"
                  dataKey="heart_rate"
                  name="Heart Rate (BPM)"
                  stroke="#2563eb"
                  strokeWidth={3}
                />

              </LineChart>

            </ResponsiveContainer>

          ) : (

            <p>
              No heart rate data available.
            </p>

          )}

        </section>



        {/* SPO2 */}

        <section className="report-section">

          <h2>
            🫁 SpO₂ Trend
          </h2>


          {vitals.length > 0 ? (

            <ResponsiveContainer
              width="100%"
              height={300}
            >

              <LineChart
                data={[...vitals].reverse()}
              >

                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis
                  dataKey="recorded_at"
                />

                <YAxis />

                <Tooltip />

                <Legend />

                <Line
                  type="monotone"
                  dataKey="spo2"
                  name="SpO₂ (%)"
                  stroke="#16a34a"
                  strokeWidth={3}
                />

              </LineChart>

            </ResponsiveContainer>

          ) : (

            <p>
              No SpO₂ data available.
            </p>

          )}

        </section>



        {/* BLOOD PRESSURE */}

        <section className="report-section">

          <h2>
            🩺 Blood Pressure Trend
          </h2>


          {vitals.length > 0 ? (

            <ResponsiveContainer
              width="100%"
              height={300}
            >

              <LineChart
                data={[...vitals].reverse()}
              >

                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis
                  dataKey="recorded_at"
                />

                <YAxis />

                <Tooltip />

                <Legend />

                <Line
                  type="monotone"
                  dataKey="systolic_bp"
                  name="Systolic"
                  stroke="#dc2626"
                  strokeWidth={3}
                />

                <Line
                  type="monotone"
                  dataKey="diastolic_bp"
                  name="Diastolic"
                  stroke="#9333ea"
                  strokeWidth={3}
                />

              </LineChart>

            </ResponsiveContainer>

          ) : (

            <p>
              No blood pressure data available.
            </p>

          )}

        </section>



        {/* TEMPERATURE */}

        <section className="report-section">

          <h2>
            🌡️ Temperature Trend
          </h2>


          {vitals.length > 0 ? (

            <ResponsiveContainer
              width="100%"
              height={300}
            >

              <LineChart
                data={[...vitals].reverse()}
              >

                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis
                  dataKey="recorded_at"
                />

                <YAxis />

                <Tooltip />

                <Legend />

                <Line
                  type="monotone"
                  dataKey="temperature"
                  name="Temperature (°C)"
                  stroke="#f59e0b"
                  strokeWidth={3}
                />

              </LineChart>

            </ResponsiveContainer>

          ) : (

            <p>
              No temperature data available.
            </p>

          )}

        </section>



        {/* MEDICAL REPORT */}

        <section className="report-section">

          <h2>
            📄 Medical Report
          </h2>


          <p>
            Upload a medical report to extract
            and understand the information inside it.
          </p>


          <div className="upload-area">


            <div>
              📁
            </div>


            <p>
              Select your PDF medical report
            </p>


            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
            />


            <br />


            {/* UPLOAD */}

            <button
              className="upload-button"
              onClick={handleUpload}
              disabled={!selectedFile}
            >
              Upload Report
            </button>


            {/* EXTRACT VITALS */}

            <button
              className="upload-button"
              onClick={handleExtractVitals}
              disabled={
                !reportText ||
                extractingVitals
              }
            >

              {extractingVitals
                ? "Extracting Vitals..."
                : "🔍 Extract Vitals from Report"}

            </button>


            {/* AI ANALYSIS */}

            <button
              className="upload-button"
              onClick={handleAnalyze}
              disabled={
                !reportText ||
                analyzing
              }
            >

              {analyzing
                ? "Analyzing Report..."
                : "🧠 Analyze Report with AI"}

            </button>


          </div>



          {/* EXTRACTED TEXT */}

          {reportText && (

            <div className="report-text">

              <h3>
                📄 Extracted Report Text
              </h3>

              <pre>
                {reportText}
              </pre>

            </div>

          )}



          {/* EXTRACTED VITALS */}

          {extractedVitals && (

            <div className="report-text">

              <h3>
                🔍 Extracted Health Values
              </h3>


              <p>

                ❤️ Heart Rate:{" "}

                {extractedVitals.heart_rate !==
                null

                  ? `${extractedVitals.heart_rate} BPM`

                  : "Not found"}

              </p>


              <p>

                🫁 SpO₂:{" "}

                {extractedVitals.spo2 !==
                null

                  ? `${extractedVitals.spo2}%`

                  : "Not found"}

              </p>


              <p>

                🩺 Blood Pressure:{" "}

                {extractedVitals.systolic_bp !==
                  null &&
                extractedVitals.diastolic_bp !==
                  null

                  ? `${extractedVitals.systolic_bp}/${extractedVitals.diastolic_bp} mmHg`

                  : "Not found"}

              </p>


              <p>

                🌡️ Temperature:{" "}

                {extractedVitals.temperature !==
                null

                  ? `${extractedVitals.temperature}°C`

                  : "Not found"}

              </p>


              <button
                className="upload-button"
                onClick={
                  handleSaveExtractedVitals
                }
              >
                💾 Save Extracted Vitals
              </button>


            </div>

          )}



          {/* AI ANALYSIS */}

          {analysis && (

            <div className="report-text">

              <h3>
                🤖 AI Report Analysis
              </h3>


              <pre>
                {analysis}
              </pre>


            </div>

          )}

        </section>



        {/* BACKEND STATUS */}

        <section className="report-section">

          <h2>
            🔗 Backend Status
          </h2>

          <p>
            Connected to HealthScan AI backend
          </p>

        </section>


      </main>

    </div>

  );

}


export default App;