"""
Employee Salary Prediction System
Salary Comparison and Prediction History (Activity 3)

System flow:
    Load Existing Saved Model -> Enter Employee Details -> Predict Salary
    -> Classify Salary Range -> Save Prediction History
    -> Compare Two Experience Levels -> Calculate Difference -> Display JSON Output

Runs completely offline. All salary values come from `salary_model.pkl`.

    python app.py      ->  open http://127.0.0.1:5000
"""

import csv
import math
import os
import threading
import uuid
from datetime import datetime

import joblib
import pandas as pd
from flask import Flask, Response, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.environ.get("SALARY_MODEL_PATH", os.path.join(BASE_DIR, "salary_model.pkl"))
HISTORY_PATH = os.environ.get("SALARY_HISTORY_PATH", os.path.join(BASE_DIR, "salary_history.csv"))

CURRENCY = "PHP"
FEATURES = ["education", "years_experience", "working_hours"]
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
# Model loading (no retraining, ever)
# --------------------------------------------------------------------------
def load_model(path=MODEL_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Saved model not found: {path}\n"
            "Copy your salary_model.pkl from Activity 1 here "
            "(or run `python train_model.py` once to create it)."
        )
    return joblib.load(path)


def supported_education_levels(model):
    """Read the education levels the ORIGINAL model was trained on."""
    for _, step in getattr(model, "steps", [("", model)]):
        transformers = getattr(step, "transformers_", None)
        if not transformers:
            continue
        for _, encoder, columns in transformers:
            if hasattr(encoder, "categories_") and "education" in list(columns):
                idx = list(columns).index("education")
                return [str(c) for c in encoder.categories_[idx]]
    raise RuntimeError("Could not read supported education levels from the saved model.")


def _order_levels(levels):
    """Display order: by the model's own baseline prediction (0 yrs, 40 hrs/week)."""
    try:
        rows = pd.DataFrame([[lvl, 0, 40] for lvl in levels], columns=FEATURES)
        preds = model.predict(rows)
        return [lvl for _, lvl in sorted(zip(preds, levels))]
    except Exception:
        return levels


model = load_model()
EDUCATION_LEVELS = _order_levels(supported_education_levels(model))

app = Flask(__name__)
app.json.sort_keys = False


# --------------------------------------------------------------------------
# Core logic
# --------------------------------------------------------------------------
def predict_salary(education, years_experience, working_hours):
    row = pd.DataFrame(
        [[education, years_experience, working_hours]], columns=FEATURES
    )
    return round(float(model.predict(row)[0]), 2)


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
                r[key] = float(r[key])
                if r[key].is_integer() and key != "predicted_salary":
                    r[key] = int(r[key])
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


def _payload():
    data = request.get_json(silent=True)
    if data is None:
        data = request.form.to_dict() or request.args.to_dict()
    return data if isinstance(data, dict) else {}


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
    if education not in EDUCATION_LEVELS:
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
# Routes
# --------------------------------------------------------------------------
@app.errorhandler(ValidationError)
def handle_validation(err):
    return jsonify({"error": "Invalid input.", "details": err.errors}), 400


@app.get("/")
def index():
    return render_template(
        "index.html",
        education_levels=EDUCATION_LEVELS,
        default_education="Bachelor's Degree" if "Bachelor's Degree" in EDUCATION_LEVELS else EDUCATION_LEVELS[0],
        low_limit=LOW_LIMIT,
        high_limit=HIGH_LIMIT,
        min_hours=MIN_HOURS,
        max_hours=MAX_HOURS,
    )


@app.get("/meta")
def meta():
    return jsonify(
        {
            "education_levels": EDUCATION_LEVELS,
            "currency": CURRENCY,
            "thresholds": {"LOW": f"< {LOW_LIMIT}", "MEDIUM": f"{LOW_LIMIT} - {HIGH_LIMIT - 0.01}", "HIGH": f">= {HIGH_LIMIT}"},
            "working_hours_range": [MIN_HOURS, MAX_HOURS],
        }
    )


@app.post("/predict")
def predict():
    data = _payload()
    errors = {}
    name, education, hours = validate_common(data, errors)
    exp = validate_experience(data, "years_experience", "Years of experience", errors)
    if errors:
        raise ValidationError(errors)

    salary = predict_salary(education, exp, hours)
    record = make_record("predict", name, education, exp, hours, salary)
    save_history([record])

    return jsonify(
        {
            "employee_name": name,
            "education": education,
            "working_hours": hours,
            "years_experience": exp,
            "predicted_salary": salary,
            "salary_range": record["salary_range"],
            "currency": CURRENCY,
            "timestamp": record["timestamp"],
        }
    )


@app.post("/compare")
def compare():
    data = _payload()
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

    return jsonify(
        {
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
    )


@app.get("/history")
def history():
    records = read_history()
    if request.args.get("format") == "csv":
        content = ""
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH, encoding="utf-8") as f:
                content = f.read()
        return Response(
            content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=salary_history.csv"},
        )
    records.reverse()  # newest first
    return jsonify({"count": len(records), "currency": CURRENCY, "records": records})


if __name__ == "__main__":
    print(f"Model loaded : {MODEL_PATH}")
    print(f"Education    : {', '.join(EDUCATION_LEVELS)}")
    print(f"History file : {HISTORY_PATH}")
    print("Open http://127.0.0.1:5000 in your browser (works offline).")
    app.run(host="127.0.0.1", port=5000, debug=False)
