from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from pypdf import PdfReader
import os
import re

from dotenv import load_dotenv
from google import genai


# -----------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# -----------------------------------
# FLASK APP
# -----------------------------------

app = Flask(__name__)
CORS(app)


# -----------------------------------
# UPLOAD FOLDER
# -----------------------------------

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# -----------------------------------
# DATABASE CONNECTION
# -----------------------------------

def get_db_connection():

    connection = mysql.connector.connect(
        host="localhost",
        user="root",
       ,password=os.getenv("12345"),
        database="healthscan"
    )

    return connection


# -----------------------------------
# HOME
# -----------------------------------

@app.route("/")
def home():

    return "HealthScan AI Backend is running!"


# -----------------------------------
# HEALTH API TEST
# -----------------------------------

@app.route("/api/health")
def health():

    return jsonify({
        "message": "HealthScan AI API is working!",
        "status": "success"
    })


# -----------------------------------
# DATABASE TEST
# -----------------------------------

@app.route("/api/db-test")
def db_test():

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT DATABASE()")

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    return jsonify({
        "database": result[0],
        "status": "connected"
    })


# -----------------------------------
# ADD VITALS
# -----------------------------------

@app.route("/api/vitals", methods=["POST"])
def add_vitals():

    data = request.json

    connection = get_db_connection()

    cursor = connection.cursor()

    query = """
        INSERT INTO vitals
        (heart_rate, spo2, systolic_bp, diastolic_bp, temperature)
        VALUES (%s, %s, %s, %s, %s)
    """

    values = (
        data["heart_rate"],
        data["spo2"],
        data["systolic_bp"],
        data["diastolic_bp"],
        data["temperature"]
    )

    cursor.execute(query, values)

    connection.commit()

    cursor.close()
    connection.close()

    return jsonify({
        "message": "Vitals saved successfully!",
        "status": "success"
    })


# -----------------------------------
# GET VITALS
# -----------------------------------

@app.route("/api/vitals", methods=["GET"])
def get_vitals():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM vitals
        ORDER BY recorded_at DESC
    """)

    vitals = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(vitals)


# -----------------------------------
# UPLOAD MEDICAL REPORT
# -----------------------------------

@app.route("/api/upload-report", methods=["POST"])
def upload_report():

    if "file" not in request.files:

        return jsonify({
            "message": "No file uploaded"
        }), 400


    file = request.files["file"]


    if file.filename == "":

        return jsonify({
            "message": "No file selected"
        }), 400


    if not file.filename.lower().endswith(".pdf"):

        return jsonify({
            "message": "Only PDF files are supported"
        }), 400


    file_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )


    file.save(file_path)


    reader = PdfReader(file_path)

    extracted_text = ""


    for page in reader.pages:

        text = page.extract_text()

        if text:

            extracted_text += text + "\n"


    return jsonify({

        "message": "Report uploaded successfully!",

        "filename": file.filename,

        "text": extracted_text

    })


# -----------------------------------
# EXTRACT VITALS FROM REPORT TEXT
# -----------------------------------

def extract_vitals_from_text(text):

    vitals = {
        "heart_rate": None,
        "spo2": None,
        "systolic_bp": None,
        "diastolic_bp": None,
        "temperature": None
    }


    # HEART RATE

    match = re.search(
        r"Heart Rate\s*[:\-]?\s*(\d+)\s*(?:bpm|BPM)?",
        text,
        re.IGNORECASE
    )

    if match:

        vitals["heart_rate"] = int(match.group(1))


    # SPO2

    match = re.search(
        r"(?:SpO2|SpO₂|Oxygen Saturation)\s*[:\-]?\s*(\d+)\s*%?",
        text,
        re.IGNORECASE
    )

    if match:

        vitals["spo2"] = int(match.group(1))


    # BLOOD PRESSURE

    match = re.search(
        r"Blood Pressure\s*[:\-]?\s*(\d+)\s*/\s*(\d+)",
        text,
        re.IGNORECASE
    )

    if match:

        vitals["systolic_bp"] = int(match.group(1))

        vitals["diastolic_bp"] = int(match.group(2))


    # TEMPERATURE

    match = re.search(
        r"Temperature\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*°?\s*C",
        text,
        re.IGNORECASE
    )

    if match:

        vitals["temperature"] = float(match.group(1))


    return vitals


# -----------------------------------
# EXTRACT VITALS API
# -----------------------------------

@app.route("/api/extract-vitals", methods=["POST"])
def extract_vitals():

    data = request.json

    report_text = data.get("text", "")


    if not report_text.strip():

        return jsonify({

            "message": "No report text provided"

        }), 400


    vitals = extract_vitals_from_text(report_text)


    return jsonify({

        "message": "Vitals extracted successfully!",

        "vitals": vitals

    })


# -----------------------------------
# ANALYZE MEDICAL REPORT WITH GEMINI
# -----------------------------------

@app.route("/api/analyze-report", methods=["POST"])
def analyze_report():

    data = request.json

    report_text = data.get("text", "")


    if not report_text.strip():

        return jsonify({

            "message": "No report text provided"

        }), 400


    prompt = f"""
You are a medical report explanation assistant.

Analyze the following medical report and explain it in
simple, easy-to-understand language.

IMPORTANT SAFETY RULES:

- Do not diagnose any disease.
- Do not prescribe medicines.
- Do not recommend treatments.
- Do not claim that the user has a medical condition.
- Use the reference ranges provided in the report when available.
- Clearly distinguish measured values from reference ranges.
- If a reference range is missing, say that it is not provided.
- Point out values that are marked abnormal by the report.
- Explain medical terms in simple language.
- Do not invent values that are not present in the report.
- Encourage the user to discuss concerning or unclear findings
  with a qualified healthcare professional.

Structure the response as:

1. Report Summary

2. Test Results

3. Explanation of the Results

4. Medical Terms Explained

5. Points to Discuss with a Healthcare Professional

Medical Report:

{report_text}
"""


    try:

        response = client.models.generate_content(

            model="gemini-3.8-flash",

            contents=prompt

        )


        return jsonify({

            "message": "Report analyzed successfully!",

            "analysis": response.text

        })


    except Exception as error:

        print("Gemini error:", error)


        return jsonify({

            "message": "Could not analyze the report.",

            "error": str(error)

        }), 500


# -----------------------------------
# RUN SERVER
# -----------------------------------

if __name__ == "__main__":

    app.run(debug=True)