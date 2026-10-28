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
from vital_extractor import extract_vitals as extract_vitals_explainably


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024


class GeminiTemporarilyUnavailable(Exception):
    """Raised after the configured Gemini model and fallbacks are overloaded."""


def _is_gemini_capacity_error(error):
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "code", None)
    try:
        if int(status) in (429, 503, 529):
            return True
    except (TypeError, ValueError):
        pass

    message = str(error).lower()
    return any(marker in message for marker in (
        "503 unavailable",
        "service unavailable",
        "currently experiencing high demand",
        "high demand",
        "temporarily unavailable",
        "model is overloaded",
        "overloaded",
        "resource_exhausted",
        "resource exhausted",
        "429 too many requests",
        "rate limit",
    ))


def generate_analysis_with_fallback(prompt):
    """Try the selected Gemini model, then alternate Flash models on capacity errors.

    Fallback is deliberately limited to temporary availability/quota errors.
    Authentication, permission, invalid-model, and malformed-request failures
    are returned immediately instead of being hidden by trying other models.
    """
    fallbacks = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash-lite"
    )
    candidates = []
    for model_name in [GEMINI_MODEL] + [
        model.strip() for model in fallbacks.split(",") if model.strip()
    ]:
        if model_name and model_name not in candidates:
            candidates.append(model_name)

    overloaded_models = []
    last_error = None

    for model_name in candidates:
        try:
            app.logger.info("Requesting report explanation using Gemini model %s", model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            analysis = getattr(response, "text", None)
            if analysis and analysis.strip():
                if overloaded_models:
                    app.logger.info(
                        "Gemini fallback succeeded with model %s after capacity errors from %s",
                        model_name,
                        ", ".join(overloaded_models)
                    )
                return response, model_name

            app.logger.warning("Gemini model %s returned an empty response.", model_name)
            last_error = RuntimeError(
                "The Gemini model returned an empty response."
            )
        except Exception as error:
            if not _is_gemini_capacity_error(error):
                raise
            last_error = error
            overloaded_models.append(model_name)
            app.logger.warning(
                "Gemini model %s is temporarily unavailable; trying the next fallback.",
                model_name
            )

    raise GeminiTemporarilyUnavailable(
        "All configured Gemini Flash models are temporarily busy. "
        "Please retry in a minute. Models tried: "
        + ", ".join(candidates)
    ) from last_error


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
    """Extract supported vital signs from selectable report text.

    This is a transparent rule-based baseline, not a clinical diagnostic
    algorithm. Values remain nullable when the source text is ambiguous.
    """
    if not isinstance(text, str):
        raise TypeError("Report text must be a string.")

    result = {
        "heart_rate": None,
        "spo2": None,
        "systolic_bp": None,
        "diastolic_bp": None,
        "temperature": None,
    }

    # Heart rate / pulse, including common abbreviations and units in brackets.
    match = re.search(
        r"\b(?:heart\s*rate|\bhr\b|pulse(?:\s*rate)?)\b"
        r"\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})\b",
        text,
        re.IGNORECASE,
    )
    if match:
        value = int(match.group(1))
        if 20 <= value <= 250:
            result["heart_rate"] = value

    # Oxygen saturation. Accept common report labels and optional percent signs.
    match = re.search(
        r"\b(?:spo\s*2|sp[o0]2|oxygen\s*saturation|o2\s*sat(?:uration)?|"
        r"oxygen\s*sat)\b"
        r"\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{1,3})\s*%?",
        text,
        re.IGNORECASE,
    )
    if match:
        value = int(match.group(1))
        if 0 <= value <= 100:
            result["spo2"] = value

    # Blood pressure as BP: 120/80, blood pressure (mmHg) 120/80, etc.
    bp_match = re.search(
        r"\b(?:blood\s*pressure|\bbp\b)\b"
        r"\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?"
        r"(\d{2,3})\s*/\s*(\d{2,3})\b",
        text,
        re.IGNORECASE,
    )
    if bp_match:
        systolic = int(bp_match.group(1))
        diastolic = int(bp_match.group(2))
        if 40 <= systolic <= 300 and 20 <= diastolic <= 200:
            result["systolic_bp"] = systolic
            result["diastolic_bp"] = diastolic
    else:
        systolic_match = re.search(
            r"\bsystolic(?:\s*(?:blood\s*pressure|bp))?\b"
            r"\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})\b",
            text,
            re.IGNORECASE,
        )
        diastolic_match = re.search(
            r"\bdiastolic(?:\s*(?:blood\s*pressure|bp))?\b"
            r"\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?(\d{2,3})\b",
            text,
            re.IGNORECASE,
        )
        if systolic_match:
            value = int(systolic_match.group(1))
            if 40 <= value <= 300:
                result["systolic_bp"] = value
        if diastolic_match:
            value = int(diastolic_match.group(1))
            if 20 <= value <= 200:
                result["diastolic_bp"] = value

    # Temperature is normalized to Celsius for consistent storage.
    match = re.search(
        r"\b(?:body\s*temperature|temperature|temp)\b"
        r"\s*(?:\([^)]{0,30}\))?\s*(?:[:=\-]\s*)?"
        r"(\d{2,3}(?:\.\d+)?)\s*°?\s*([CF])?\b",
        text,
        re.IGNORECASE,
    )
    if match:
        temperature = float(match.group(1))
        unit = (match.group(2) or "").upper()
        if unit == "F":
            temperature = (temperature - 32) * 5 / 9
        if 25 <= temperature <= 45:
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
            return jsonify({"message": "No report text provided."}), 400
        if len(text) > 250_000:
            return jsonify({
                "message": "Report text is too long for extraction (maximum 250,000 characters)."
            }), 413

        # Run the explainable engine for source evidence, rule names, coverage
        # metadata, and warnings. The guarded baseline is used for displayed
        # values so obvious out-of-bound parsing artifacts are not silently saved.
        explainable = extract_vitals_explainably(text)
        raw_vitals = (explainable.get("vitals") or {})
        vitals = extract_vitals_from_text(text)
        evidence = {}
        validation_notes = list(explainable.get("validation_notes") or [])
        flagged_fields = {note.get("field") for note in validation_notes}

        for field, value in vitals.items():
            raw_value = raw_vitals.get(field)
            if value is not None and raw_value == value:
                source = (explainable.get("evidence") or {}).get(field)
                if source:
                    evidence[field] = source
            elif raw_value is not None and value is None and field not in flagged_fields:
                validation_notes.append({
                    "field": field,
                    "label": field.replace("_", " ").title(),
                    "value": raw_value,
                    "message": (
                        "A labelled candidate was detected, but the guarded parser "
                        "did not return it. Verify the source line, units, and format."
                    ),
                })

        found_count = sum(value is not None for value in vitals.values())
        quality = dict(explainable.get("quality") or {})
        quality["fields_found"] = found_count
        quality["fields_supported"] = len(vitals)
        quality["coverage_percent"] = round(found_count / max(len(vitals), 1) * 100, 1)
        quality["note"] = (
            "Coverage is the share of supported fields detected in this text; "
            "it is not extraction accuracy or a clinical assessment."
        )

        return jsonify({
            "message": "Explainable vital extraction completed. Verify every value against the source PDF.",
            "vitals": vitals,
            "found_count": found_count,
            "extraction_method": "label-aware regular expressions with source evidence",
            "engine": explainable.get("engine", "HealthScan Explainable Extractor"),
            "evidence": evidence,
            "quality": quality,
            "validation_notes": validation_notes,
            "disclaimer": (
                "This parser may miss alternate layouts or associate a nearby number with "
                "a label. Values and trends are informational only, not a diagnosis."
            ),
        }), 200

    except Exception:
        app.logger.exception("EXTRACT VITALS ERROR")
        return jsonify({
            "message": "Could not extract vitals. Check the text format and try again."
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
                    "AI analysis is not configured on the server. Add a valid "
                    "GEMINI_API_KEY in Render → your backend service → Environment, "
                    "then redeploy the backend. The extracted PDF text remains available."
                ),
                "code": "MISSING_GEMINI_API_KEY"
            }), 503

        prompt = f"""
You are a careful medical-report explanation assistant. Your job is different
from a vital-value extraction tool: do not return JSON, do not simply copy the
report text, and do not merely repeat a list of vital measurements.

Explain the report to a non-specialist in concise, plain language. Interpret
what the report itself says and how its findings relate to one another, while
being explicit about uncertainty.

Safety and accuracy rules:
- Do not diagnose, prescribe medicine, or recommend changing treatment.
- Never invent measurements, clinical history, or laboratory reference ranges.
- Only call a value high, low, normal, or abnormal if the report provides a
  reference range or explicit flag that supports that description.
- Distinguish the report's stated findings from general explanatory context.
- If a value or section is not present, say the report does not provide it.
- Avoid repeating the whole report or reproducing the raw extracted-vitals list.
- End by encouraging the user to discuss important findings with a qualified
  healthcare professional.

Write these exact section headings, each on its own line:
1. Report Summary
Give a short narrative overview of the document and its main stated purpose.
2. Important Values
Explain only the most relevant findings in context; do not just list numbers.
3. Values Outside the Given Reference Range
Discuss only values the report explicitly flags or supplies reference ranges for.
If none are identifiable from the report, say that clearly.
4. Simple Explanation
Explain the report's meaning and limitations in everyday language, without
making a diagnosis.
5. Questions to Ask a Doctor
Suggest a few practical questions based on the report contents.

Medical report text:
{text}
"""

        response, used_model = generate_analysis_with_fallback(prompt)
        app.logger.info("Report explanation generated by Gemini model %s", used_model)

        analysis = getattr(response, "text", None)

        if not analysis or not analysis.strip():
            return jsonify({
                "message": "Gemini returned an empty response."
            }), 502

        # The AI response should still be returned if persistence fails. The
        # UI can show the explanation immediately, with a clear warning that
        # it could not be stored in report history.
        database_saved = False
        persistence_warning = None

        if report_id is not None:
            try:
                report_id = int(report_id)
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
                    persistence_warning = (
                        "The AI explanation was generated, but the uploaded "
                        "report was not found in history, so the explanation was not saved."
                    )
                else:
                    db.commit()
                    database_saved = True
            except Exception:
                if db:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                app.logger.exception(
                    "AI EXPLANATION GENERATED BUT COULD NOT BE SAVED TO REPORT HISTORY"
                )
                persistence_warning = (
                    "The AI explanation was generated, but it could not be saved "
                    "to report history. You can still read the result below."
                )
            finally:
                close_db(cursor, db)
                cursor = None
                db = None

        return jsonify({
            "message": persistence_warning or "Report analysis completed.",
            "analysis": analysis,
            "report_id": report_id,
            "database_saved": database_saved,
            "warning": persistence_warning
        }), 200

    except GeminiTemporarilyUnavailable as e:
        app.logger.warning("All Gemini fallback models are temporarily unavailable: %s", e)
        return jsonify({
            "message": str(e),
            "code": "GEMINI_TEMPORARILY_UNAVAILABLE",
            "retryable": True
        }), 503

    except Exception as e:
        app.logger.exception("GEMINI ANALYSIS ERROR")
        error_text = str(e)
        app.logger.error("AI provider failure details: %s", error_text)
        return jsonify({
            "message": (
                "The AI provider could not generate an explanation. Check the "
                "GEMINI_API_KEY, configured model, API quota, and Render logs."
            ),
            "error": error_text,
            "code": "AI_PROVIDER_ERROR"
        }), 502

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
