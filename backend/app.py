from flask import Flask, jsonify, request
from flask_cors import CORS

import mysql.connector
import os
import re
from threading import Lock

from dotenv import load_dotenv
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024


# ============================================================
# DATABASE CONNECTION
# ============================================================

# Create the tables this application requires when the database is empty.
# This is intentionally limited to CREATE TABLE IF NOT EXISTS; it does not
# delete or overwrite existing user data.
_SCHEMA_INITIALIZED = False
_SCHEMA_LOCK = Lock()


def _ensure_database_schema(connection):
    global _SCHEMA_INITIALIZED

    if _SCHEMA_INITIALIZED:
        return

    with _SCHEMA_LOCK:
        if _SCHEMA_INITIALIZED:
            return

        statements = [
            """
            CREATE TABLE IF NOT EXISTS vitals (
                id INT NOT NULL AUTO_INCREMENT,
                heart_rate INT NULL,
                spo2 INT NULL,
                systolic_bp INT NULL,
                diastolic_bp INT NULL,
                temperature FLOAT NULL,
                recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                INDEX idx_vitals_recorded_at (recorded_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INT NOT NULL AUTO_INCREMENT,
                filename VARCHAR(255) NOT NULL,
                report_text LONGTEXT NOT NULL,
                ai_analysis LONGTEXT NULL,
                uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                INDEX idx_reports_uploaded_at (uploaded_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT NOT NULL AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(191) NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_users_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]

        cursor = None
        try:
            cursor = connection.cursor()
            for statement in statements:
                cursor.execute(statement)
            connection.commit()
            _SCHEMA_INITIALIZED = True
            app.logger.info("HealthScan AI database schema is ready.")
        except Exception:
            try:
                connection.rollback()
            except Exception:
                pass
            app.logger.exception("Could not initialize HealthScan AI database schema.")
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass


def get_db_connection():
    """Connect to MySQL and initialize required tables if the database is empty."""
    connection_options = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "healthscan"),
        "connection_timeout": 20,
    }

    # Aiven connections require SSL. Supply MYSQL_SSL_CA to verify the Aiven
    # CA certificate when it is configured as a Render Secret File.
    ssl_ca = os.getenv("MYSQL_SSL_CA")
    if ssl_ca:
        connection_options["ssl_ca"] = ssl_ca
        connection_options["ssl_verify_cert"] = True
        connection_options["ssl_verify_identity"] = True

    connection = mysql.connector.connect(**connection_options)
    try:
        _ensure_database_schema(connection)
        return connection
    except Exception:
        connection.close()
        raise


# ============================================================
# HELPER: DATABASE CLEANUP
# ============================================================

def close_db(cursor=None, db=None):
    if cursor is not None:
        try:
            cursor.close()
        except Exception:
            pass

    if db is not None:
        try:
            db.close()
        except Exception:
            pass


# ============================================================
# HOME AND HEALTH CHECK
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "message": "HealthScan AI Backend is running!"
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "message": "HealthScan AI API is working"
    })


@app.route("/api/db-test")
def db_test():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        return jsonify({
            "database": "connected",
            "result": result[0]
        })

    except Exception as e:
        app.logger.exception("DATABASE TEST ERROR")
        return jsonify({
            "database": "error",
            "message": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# SIGNUP
# ============================================================

@app.route("/api/signup", methods=["POST"])
def signup():
    db = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            return jsonify({
                "message": "Please fill in all fields."
            }), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        if cursor.fetchone():
            return jsonify({
                "message": "Email already registered."
            }), 409

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (%s, %s, %s)
            """,
            (name, email, hashed_password)
        )

        db.commit()

        return jsonify({
            "message": "Account created successfully!"
        }), 201

    except Exception as e:
        if db:
            db.rollback()

        app.logger.exception("SIGNUP ERROR")

        return jsonify({
            "message": "Signup failed.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# LOGIN
# ============================================================

@app.route("/api/login", methods=["POST"])
def login():
    db = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({
                "message": "Please enter email and password."
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, name, email, password FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        if not user or not check_password_hash(
            user["password"], password
        ):
            return jsonify({
                "message": "Invalid email or password."
            }), 401

        return jsonify({
            "message": "Login successful!",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }), 200

    except Exception as e:
        app.logger.exception("LOGIN ERROR")

        return jsonify({
            "message": "Login failed.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# SAVE VITALS
# ============================================================

@app.route("/api/vitals", methods=["POST"])
def save_vitals():
    db = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        fields = [
            "heart_rate",
            "spo2",
            "systolic_bp",
            "diastolic_bp",
            "temperature"
        ]

        values = [data.get(field) for field in fields]

        if all(value is None for value in values):
            return jsonify({
                "message": "Provide at least one vital value."
            }), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO vitals
            (
                heart_rate, spo2, systolic_bp,
                diastolic_bp, temperature
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            tuple(values)
        )

        db.commit()

        return jsonify({
            "message": "Vitals saved successfully!"
        }), 201

    except Exception as e:
        if db:
            db.rollback()

        app.logger.exception("SAVE VITALS ERROR")

        return jsonify({
            "message": "Could not save vitals.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# GET VITALS
# ============================================================

@app.route("/api/vitals", methods=["GET"])
def get_vitals():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, heart_rate, spo2, systolic_bp,
                   diastolic_bp, temperature, recorded_at
            FROM vitals
            ORDER BY recorded_at ASC
            """
        )

        vitals = cursor.fetchall()

        for item in vitals:
            if item.get("recorded_at"):
                item["recorded_at"] = item[
                    "recorded_at"
                ].strftime("%Y-%m-%d %H:%M:%S")

        return jsonify(vitals)

    except Exception as e:
        app.logger.exception("GET VITALS ERROR")

        return jsonify({
            "message": "Could not load vitals.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# GET REPORTS
# ============================================================

@app.route("/api/reports", methods=["GET"])
def get_reports():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, filename, report_text,
                   ai_analysis, uploaded_at
            FROM reports
            ORDER BY uploaded_at DESC
            """
        )

        reports = cursor.fetchall()

        for report in reports:
            if report.get("uploaded_at"):
                report["uploaded_at"] = report[
                    "uploaded_at"
                ].strftime("%Y-%m-%d %H:%M:%S")

        return jsonify(reports)

    except Exception as e:
        app.logger.exception("GET REPORTS ERROR")

        return jsonify({
            "message": "Could not load reports.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# UPLOAD PDF REPORT
# ============================================================

@app.route("/api/upload-report", methods=["POST"])
def upload_report():
    db = None
    cursor = None
    filepath = None

    try:
        if "file" not in request.files:
            return jsonify({
                "message": "No file uploaded."
            }), 400

        file = request.files["file"]

        if not file.filename:
            return jsonify({
                "message": "No file selected."
            }), 400

        filename = secure_filename(file.filename)

        if not filename or not filename.lower().endswith(".pdf"):
            return jsonify({
                "message": "Only PDF files are supported."
            }), 400

        # Use a unique filename to avoid overwriting other uploads.
        import uuid
        stored_filename = f"{uuid.uuid4().hex}_{filename}"

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            stored_filename
        )

        file.save(filepath)

        reader = PdfReader(filepath)
        pages_text = []

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)

        report_text = "\n".join(pages_text).strip()

        if not report_text:
            return jsonify({
                "message": (
                    "No selectable text was found in this PDF. "
                    "It may be a scanned image and require OCR."
                ),
                "text": ""
            }), 422

        # Persist the report when the database is available. If the managed
        # database is temporarily unavailable, still return extracted text so
        # the user can extract vitals and request AI analysis; be explicit that
        # the report was not saved.
        report_id = None
        database_saved = False
        response_message = (
            "Report text extracted. You can now extract vitals or analyze it."
        )

        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT INTO reports (filename, report_text)
                VALUES (%s, %s)
                """,
                (filename, report_text)
            )
            db.commit()
            report_id = cursor.lastrowid
            database_saved = True
            response_message = "Report uploaded and saved successfully!"
        except Exception:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            app.logger.exception(
                "REPORT TEXT EXTRACTED BUT DATABASE SAVE FAILED"
            )
            response_message = (
                "Report text was extracted, but the database is unavailable, "
                "so the report was not saved. You can still extract vitals "
                "and analyze this report; saving and history require the "
                "database connection to be restored."
            )

        return jsonify({
            "message": response_message,
            "report_id": report_id,
            "database_saved": database_saved,
            "filename": filename,
            "text": report_text
        }), 201

    except Exception as e:
        if db:
            db.rollback()

        app.logger.exception("UPLOAD REPORT ERROR")

        return jsonify({
            "message": "Could not process report.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# EXTRACT VITALS FROM REPORT TEXT
# ============================================================

def extract_vitals_from_text(text):
    result = {
        "heart_rate": None,
        "spo2": None,
        "systolic_bp": None,
        "diastolic_bp": None,
        "temperature": None
    }

    # Heart rate or pulse
    match = re.search(
        r"\b(?:heart\s*rate|pulse(?:\s*rate)?)\b"
        r"\s*(?:[:=\-]\s*)?(\d{2,3})\b",
        text,
        re.IGNORECASE
    )

    if match:
        result["heart_rate"] = int(match.group(1))

    # Oxygen saturation
    match = re.search(
        r"\b(?:spo\s*2|spo2|oxygen\s*saturation)"
        r"\b\s*(?:[:=\-]\s*)?(\d{1,3})\s*%?",
        text,
        re.IGNORECASE
    )

    if match:
        result["spo2"] = int(match.group(1))

    # Blood pressure such as BP: 120/80
    match = re.search(
        r"\b(?:blood\s*pressure|bp)\b"
        r"\s*(?:[:=\-]\s*)?(\d{2,3})\s*/\s*(\d{2,3})\b",
        text,
        re.IGNORECASE
    )

    if match:
        result["systolic_bp"] = int(match.group(1))
        result["diastolic_bp"] = int(match.group(2))
    else:
        # Alternative labels, if both are present
        systolic = re.search(
            r"\bsystolic(?:\s*blood\s*pressure)?\b"
            r"\s*(?:[:=\-]\s*)?(\d{2,3})\b",
            text,
            re.IGNORECASE
        )

        diastolic = re.search(
            r"\bdiastolic(?:\s*blood\s*pressure)?\b"
            r"\s*(?:[:=\-]\s*)?(\d{2,3})\b",
            text,
            re.IGNORECASE
        )

        if systolic:
            result["systolic_bp"] = int(systolic.group(1))

        if diastolic:
            result["diastolic_bp"] = int(diastolic.group(1))

    # Temperature; retain the number as printed.
    match = re.search(
        r"\b(?:body\s*)?temperature\b"
        r"\s*(?:[:=\-]\s*)?(\d{2,3}(?:\.\d+)?)"
        r"\s*°?\s*([CF])?\b",
        text,
        re.IGNORECASE
    )

    if match:
        temperature = float(match.group(1))
        unit = (match.group(2) or "").upper()

        # Convert Fahrenheit to Celsius for database consistency.
        if unit == "F":
            temperature = (temperature - 32) * 5 / 9

        result["temperature"] = round(temperature, 2)

    return result


# ============================================================
# EXTRACT VITALS API
# ============================================================

@app.route("/api/extract-vitals", methods=["POST"])
def extract_vitals():
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")

        if not isinstance(text, str) or not text.strip():
            return jsonify({
                "message": "No report text provided."
            }), 400

        vitals = extract_vitals_from_text(text)

        return jsonify({
            "message": "Vital extraction completed.",
            "vitals": vitals,
            "found_count": sum(
                value is not None for value in vitals.values()
            )
        }), 200

    except Exception as e:
        app.logger.exception("EXTRACT VITALS ERROR")

        return jsonify({
            "message": "Could not extract vitals.",
            "error": str(e)
        }), 500


# ============================================================
# GEMINI REPORT ANALYSIS
# ============================================================

@app.route("/api/analyze-report", methods=["POST"])
def analyze_report():
    db = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        text = data.get("text", "")
        report_id = data.get("report_id")

        if not isinstance(text, str) or not text.strip():
            return jsonify({
                "message": "No report text provided."
            }), 400

        if not client:
            return jsonify({
                "message": (
                    "GEMINI_API_KEY is missing. "
                    "Add it to your .env file and restart Flask."
                )
            }), 500

        prompt = f"""
You are a health report explanation assistant.

Explain this report in simple language.

Rules:
- Do not diagnose the patient.
- Do not prescribe medicines.
- Do not invent values or reference ranges.
- Distinguish information printed in the report from general context.
- Explain abnormal values only when supported by the report.
- Encourage consultation with a qualified healthcare professional.

Use these sections:
1. Report Summary
2. Important Values
3. Values Outside the Given Reference Range
4. Simple Explanation
5. Questions to Ask a Doctor

If a section has insufficient information, say so.

Medical report:
{text}
"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        analysis = getattr(response, "text", None)

        if not analysis or not analysis.strip():
            return jsonify({
                "message": "Gemini returned an empty response."
            }), 502

        # Save analysis when the frontend supplies the uploaded report ID.
        if report_id is not None:
            try:
                report_id = int(report_id)
            except (ValueError, TypeError):
                return jsonify({
                    "message": "Invalid report_id."
                }), 400

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                """
                UPDATE reports
                SET ai_analysis = %s
                WHERE id = %s
                """,
                (analysis, report_id)
            )

            if cursor.rowcount == 0:
                db.rollback()
                return jsonify({
                    "message": "Report not found; analysis was not saved."
                }), 404

            db.commit()

        return jsonify({
            "message": "Report analysis completed.",
            "analysis": analysis,
            "report_id": report_id
        }), 200

    except Exception as e:
        if db:
            db.rollback()

        app.logger.exception("GEMINI ANALYSIS ERROR")

        return jsonify({
            "message": "AI analysis failed.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# SAVE OR UPDATE ANALYSIS SEPARATELY
# ============================================================

@app.route(
    "/api/reports/<int:report_id>/analysis",
    methods=["PUT"]
)
def save_analysis(report_id):
    db = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}
        analysis = data.get("analysis", "")

        if not isinstance(analysis, str) or not analysis.strip():
            return jsonify({
                "message": "No analysis provided."
            }), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            UPDATE reports
            SET ai_analysis = %s
            WHERE id = %s
            """,
            (analysis, report_id)
        )

        if cursor.rowcount == 0:
            db.rollback()
            return jsonify({
                "message": "Report not found."
            }), 404

        db.commit()

        return jsonify({
            "message": "AI analysis saved successfully!"
        }), 200

    except Exception as e:
        if db:
            db.rollback()

        app.logger.exception("SAVE ANALYSIS ERROR")

        return jsonify({
            "message": "Could not save AI analysis.",
            "error": str(e)
        }), 500

    finally:
        close_db(cursor, db)


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
