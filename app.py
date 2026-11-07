"""
Employee Salary Prediction System
Salary Comparison and Prediction History (Activity 3)

System flow:
    Load Existing Saved Model -> Enter Employee Details -> Predict Salary
    -> Classify Salary Range -> Save Prediction History
    -> Compare Two Experience Levels -> Calculate Difference -> Display JSON Output

Uses ONLY the Python standard library and runs completely offline.
Every salary value comes from the saved Activity 1 model, `salary_model.pkl`.

    python app.py               ->  starts the server AND opens the browser automatically
    python app.py --no-browser  ->  starts the server only
"""

import csv
import html
import json
import math
import mimetypes
import os
import pickle
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Same as http.server.ThreadingHTTPServer (3.7+), defined here so Python 3.6 works too."""

    daemon_threads = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.environ.get("SALARY_MODEL_PATH", os.path.join(BASE_DIR, "salary_model.pkl"))
HISTORY_PATH = os.environ.get("SALARY_HISTORY_PATH", os.path.join(BASE_DIR, "salary_history.csv"))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "index.html")
STATIC_DIR = os.path.join(BASE_DIR, "static")

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", "5000"))
CURRENCY = "PHP"
MIN_HOURS, MAX_HOURS = 1, 168

# Fixed classification thresholds (monthly salary, PHP)
LOW_LIMIT = 20000
HIGH_LIMIT = 50000

HISTORY_FIELDS = [
    "timestamp",
    "request_type",
    "comparison_id",
    "employee_name",
    "education",
    "years_experience",
    "working_hours",
    "predicted_salary",
    "salary_range",
    "currency",
]

_history_lock = threading.Lock()


# --------------------------------------------------------------------------
# Model loading (the Activity 1 model is used as-is — never retrained)
# --------------------------------------------------------------------------
# salary_model.pkl from Activity 1 is a dictionary:
#   {
#     "coefficients": [intercept, b_education, b_experience, b_hours],
#     "education": {"High School": 0, "Associate Degree": 1, ...},
#     "training_records": 24,
#   }
# predicted monthly salary =
#   intercept + b_education * education_code + b_experience * years + b_hours * hours
def load_model(path=MODEL_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Saved model not found: {path}\n"
            "Copy salary_model.pkl from Laboratory Activity 1 next to app.py."
        )
    with open(path, "rb") as f:
        data = pickle.load(f)
    if not isinstance(data, dict) or "coefficients" not in data or "education" not in data:
        raise ValueError("salary_model.pkl must contain 'coefficients' and 'education'.")
    if len(data["coefficients"]) != 4:
        raise ValueError("Expected 4 coefficients: intercept, education, experience, hours.")
    return data


model = load_model()
COEFFICIENTS = [float(c) for c in model["coefficients"]]
EDUCATION_CODES = {str(k): v for k, v in model["education"].items()}
# Education levels supported by the ORIGINAL model, in their encoded order
EDUCATION_LEVELS = sorted(EDUCATION_CODES, key=EDUCATION_CODES.get)


# --------------------------------------------------------------------------
# Core logic
# --------------------------------------------------------------------------
def predict_salary(education, years_experience, working_hours):
    intercept, b_edu, b_exp, b_hours = COEFFICIENTS
    salary = (
        intercept
        + b_edu * EDUCATION_CODES[education]
        + b_exp * years_experience
        + b_hours * working_hours
    )
    return round(salary, 2)


def classify_salary(salary):
    if salary < LOW_LIMIT:
        return "LOW"
    if salary < HIGH_LIMIT:
        return "MEDIUM"
    return "HIGH"


def save_history(records):
    with _history_lock:
        new_file = not os.path.exists(HISTORY_PATH) or os.path.getsize(HISTORY_PATH) == 0
        with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerows(records)


def read_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with _history_lock, open(HISTORY_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for key in ("years_experience", "working_hours", "predicted_salary"):
            try:
                value = float(r[key])
                r[key] = int(value) if value.is_integer() and key != "predicted_salary" else value
            except (TypeError, ValueError):
                pass
    return rows


def make_record(request_type, name, education, exp, hours, salary, comparison_id=""):
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "request_type": request_type,
        "comparison_id": comparison_id,
        "employee_name": name,
        "education": education,
        "years_experience": exp,
        "working_hours": hours,
        "predicted_salary": salary,
        "salary_range": classify_salary(salary),
        "currency": CURRENCY,
    }


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Invalid input")
        self.errors = errors


def _number(data, key, label, errors):
    raw = data.get(key)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        errors[key] = f"{label} is required."
        return None
    if isinstance(raw, bool):
        errors[key] = f"{label} must be a number."
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        errors[key] = f"{label} must be a number."
        return None
    if not math.isfinite(value):
        errors[key] = f"{label} must be a finite number."
        return None
    return int(value) if value.is_integer() else value


def validate_common(data, errors):
    name = str(data.get("employee_name") or "").strip()
    if not name:
        errors["employee_name"] = "Employee name must not be empty."

    education = str(data.get("education") or "").strip()
    if education not in EDUCATION_CODES:
        errors["education"] = "Education must be one of: " + ", ".join(EDUCATION_LEVELS) + "."

    hours = _number(data, "working_hours", "Working hours", errors)
    if hours is not None and not (MIN_HOURS <= hours <= MAX_HOURS):
        errors["working_hours"] = f"Working hours must be between {MIN_HOURS} and {MAX_HOURS} per week."
    return name, education, hours


def validate_experience(data, key, label, errors):
    exp = _number(data, key, label, errors)
    if exp is not None and exp < 0:
        errors[key] = f"{label} must be 0 or greater."
    return exp


# --------------------------------------------------------------------------
# Endpoint handlers (return plain dicts)
# --------------------------------------------------------------------------
def handle_predict(data):
    errors = {}
    name, education, hours = validate_common(data, errors)
    exp = validate_experience(data, "years_experience", "Years of experience", errors)
    if errors:
        raise ValidationError(errors)

    salary = predict_salary(education, exp, hours)
    record = make_record("predict", name, education, exp, hours, salary)
    save_history([record])
    return {
        "employee_name": name,
        "education": education,
        "working_hours": hours,
        "years_experience": exp,
        "predicted_salary": salary,
        "salary_range": record["salary_range"],
        "currency": CURRENCY,
        "timestamp": record["timestamp"],
    }


def handle_compare(data):
    errors = {}
    name, education, hours = validate_common(data, errors)
    exp1 = validate_experience(data, "experience_1", "Experience 1", errors)
    exp2 = validate_experience(data, "experience_2", "Experience 2", errors)
    if exp1 is not None and exp2 is not None and exp1 == exp2 and "experience_2" not in errors:
        errors["experience_2"] = "Use two different years-of-experience values."
    if errors:
        raise ValidationError(errors)

    salary1 = predict_salary(education, exp1, hours)
    salary2 = predict_salary(education, exp2, hours)
    comparison_id = uuid.uuid4().hex[:8]
    rec1 = make_record("compare", name, education, exp1, hours, salary1, comparison_id)
    rec2 = make_record("compare", name, education, exp2, hours, salary2, comparison_id)
    save_history([rec1, rec2])  # a comparison saves BOTH predictions

    return {
        "employee_name": name,
        "education": education,
        "working_hours": hours,
        "experience_1": exp1,
        "experience_2": exp2,
        "predicted_salary_1": salary1,
        "predicted_salary_2": salary2,
        "salary_difference": round(salary2 - salary1, 2),
        "salary_range_1": rec1["salary_range"],
        "salary_range_2": rec2["salary_range"],
        "currency": CURRENCY,
        "comparison_id": comparison_id,
        "timestamp": rec2["timestamp"],
    }


def handle_history():
    records = read_history()
    records.reverse()  # newest first
    return {"count": len(records), "currency": CURRENCY, "records": records}


def handle_meta():
    return {
        "education_levels": EDUCATION_LEVELS,
        "currency": CURRENCY,
        "thresholds": {
            "LOW": f"below {LOW_LIMIT:,}",
            "MEDIUM": f"{LOW_LIMIT:,} to {HIGH_LIMIT - 0.01:,.2f}",
            "HIGH": f"{HIGH_LIMIT:,} and above",
        },
        "working_hours_range": [MIN_HOURS, MAX_HOURS],
        "training_records": model.get("training_records"),
    }


def render_index():
    default = "Bachelor's Degree" if "Bachelor's Degree" in EDUCATION_CODES else EDUCATION_LEVELS[0]
    chips = "\n".join(
        '<label class="chip"><input type="radio" name="education" value="{v}"{c}><span>{v}</span></label>'.format(
            v=html.escape(level, quote=True), c=" checked" if level == default else ""
        )
        for level in EDUCATION_LEVELS
    )
    footer = (
        f"LOW &lt; ₱{LOW_LIMIT:,} · MEDIUM ₱{LOW_LIMIT:,}–₱{HIGH_LIMIT - 0.01:,.2f} · "
        f"HIGH ≥ ₱{HIGH_LIMIT:,}"
    )
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        page = f.read()
    values = {
        "education_chips": chips,
        "footer_ranges": footer,
        "low_limit": LOW_LIMIT,
        "high_limit": HIGH_LIMIT,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
    }
    for key, value in values.items():
        page = page.replace("{{ " + key + " }}", str(value))
    return page


# --------------------------------------------------------------------------
# HTTP server (standard library only)
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SalaryScope/1.0"

    def _send(self, status, body, content_type="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, indent=2)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _payload(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        ctype = self.headers.get("Content-Type", "")
        if "application/json" in ctype:
            try:
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            return self._send(200, render_index(), "text/html; charset=utf-8")
        if path == "/history":
            if parse_qs(url.query).get("format") == ["csv"]:
                content = b""
                if os.path.exists(HISTORY_PATH):
                    with open(HISTORY_PATH, "rb") as f:
                        content = f.read()
                return self._send(
                    200, content, "text/csv; charset=utf-8",
                    {"Content-Disposition": "attachment; filename=salary_history.csv"},
                )
            return self._send(200, handle_history())
        if path == "/meta":
            return self._send(200, handle_meta())
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        self._send(404, {"error": "Not found."})

    def do_POST(self):
        path = urlparse(self.path).path
        routes = {"/predict": handle_predict, "/compare": handle_compare}
        if path not in routes:
            return self._send(404, {"error": "Not found."})
        data = self._payload()
        if data is None:
            return self._send(400, {"error": "Request body must be a JSON object."})
        try:
            self._send(200, routes[path](data))
        except ValidationError as err:
            self._send(400, {"error": "Invalid input.", "details": err.errors})

    def _serve_static(self, rel):
        full = os.path.realpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": "Not found."})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def log_message(self, fmt, *args):
        print(f"[{datetime.now():%H:%M:%S}] {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")


def create_server(host=HOST, port=PORT):
    return ThreadingHTTPServer((host, port), Handler)


def start_server(host=HOST, first_port=PORT, tries=10):
    """Start on the first free port (5000, 5001, ...) in case one is busy."""
    for port in range(first_port, first_port + tries):
        try:
            return create_server(host, port)
        except OSError:
            print(f"Port {port} is busy, trying {port + 1}...")
    raise OSError(f"No free port found between {first_port} and {first_port + tries - 1}.")


def open_browser(url):
    """Open the local page automatically. 127.0.0.1 is this computer, so no internet is needed."""
    try:
        webbrowser.open(url, new=2)
    except Exception:
        print(f"Could not open the browser automatically. Please open {url}")


if __name__ == "__main__":
    server = start_server()
    url = f"http://{HOST}:{server.server_address[1]}"

    print("=" * 60)
    print(" SalaryScope - Employee Salary Prediction System (OFFLINE)")
    print("=" * 60)
    print(f" Model loaded : {MODEL_PATH}")
    print(f" Coefficients : {COEFFICIENTS}")
    print(f" Education    : {', '.join(EDUCATION_LEVELS)}")
    print(f" History file : {HISTORY_PATH}")
    print(f" Running at   : {url}")
    print(" Press Ctrl+C to stop.")
    print("=" * 60)

    if "--no-browser" not in sys.argv:
        # Wait a moment so the server is ready, then open the browser.
        threading.Timer(1.0, open_browser, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
