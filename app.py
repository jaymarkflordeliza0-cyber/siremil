# -*- coding: utf-8 -*-
"""
Employee Salary Prediction System
Salary Comparison and Prediction History (Activity 3)

System flow:
    Load Existing Saved Model -> Enter Employee Details -> Predict Salary
    -> Classify Salary Range -> Save Prediction History
    -> Compare Two Experience Levels -> Calculate Difference -> Display JSON Output

Works on Python 2.7 and every Python 3 version.
Uses ONLY the Python standard library and runs completely offline.
Every salary value comes from the saved Activity 1 model, `salary_model.pkl`.

    python app.py               ->  starts the server AND opens the browser automatically
    python app.py --no-browser  ->  starts the server only
"""

from __future__ import division, print_function

import csv
import io
import json
import os
import pickle
import struct
import sys
import threading
import uuid
import webbrowser
from datetime import datetime

# ---- Python 2 / Python 3 compatibility -----------------------------------
PY2 = sys.version_info[0] == 2

if PY2:  # Python 2.7
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn
    from urlparse import parse_qs, urlparse
    from cgi import escape as _escape

    text_type = unicode  # noqa: F821  (only exists on Python 2)
    string_types = (str, unicode)  # noqa: F821
else:  # Python 3.x
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    from urllib.parse import parse_qs, urlparse

    try:
        from html import escape as _escape
    except ImportError:  # Python 3.0 / 3.1
        from cgi import escape as _escape

    text_type = str
    string_types = (str,)

try:
    from collections import OrderedDict  # keeps JSON fields in a fixed order
except ImportError:  # Python 3.0
    OrderedDict = dict

import mimetypes


def html_escape(value):
    return _escape(value, True).replace("'", "&#x27;")


def to_text(value):
    """Return value as unicode text on both Python 2 and Python 3."""
    if isinstance(value, bytes) and not isinstance(value, text_type):
        return value.decode("utf-8")
    return text_type(value)


def is_finite(x):
    return not (x != x or x in (float("inf"), float("-inf")))


def money(value, decimals=0):
    """Format a number like 20,000 or 49,999.99 (works on every Python version)."""
    text = ("%." + str(decimals) + "f") % value
    whole, _, frac = text.partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return sign + ",".join(groups) + ("." + frac if frac else "")


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ---- Settings ------------------------------------------------------------
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
# Model loading (the Activity 1 model is used as-is - never retrained)
# --------------------------------------------------------------------------
# salary_model.pkl is created by train_model.py (Activity 1). It is a dictionary:
#   {
#     "coefficients": [intercept, b_education, b_experience, b_hours],
#     "education": {"High School": 0, "Associate Degree": 1, ...},
#     "training_records": 24,
#   }
# predicted monthly salary =
#   intercept + b_education * education_code + b_experience * years + b_hours * hours


def read_simple_pickle(data):
    """
    Read a pickle that holds only plain data (dict, list, tuple, str, int,
    float, bool, None) - for any pickle protocol 0 to 5.

    Python 2.7 and Python 3.0-3.3 cannot read pickle protocol 4 (the format
    of salary_model.pkl). This small reader lets those versions load the
    SAME file without changing or retraining the model. It never runs code
    from the file.
    """
    buf = bytearray(data)
    pos = [0]
    stack, marks, memo = [], [], {}

    def take(n):
        start = pos[0]
        if start + n > len(buf):
            raise ValueError("salary_model.pkl is incomplete.")
        pos[0] = start + n
        return bytes(buf[start:start + n])

    def take_line():
        end = buf.find(b"\n", pos[0])
        if end < 0:
            raise ValueError("salary_model.pkl is incomplete.")
        line = bytes(buf[pos[0]:end])
        pos[0] = end + 1
        return line

    def pop_mark():
        items = stack[marks[-1]:]
        del stack[marks.pop():]
        return items

    def text(raw):
        return raw.decode("utf-8")

    while True:
        op = chr(bytearray(take(1))[0])
        if op == "\x80":    # PROTO
            take(1)
        elif op == "\x95":  # FRAME
            take(8)
        elif op == ".":     # STOP
            return stack.pop()
        elif op == "(":     # MARK
            marks.append(len(stack))
        elif op == "}":     # EMPTY_DICT
            stack.append({})
        elif op == "]":     # EMPTY_LIST
            stack.append([])
        elif op == ")":     # EMPTY_TUPLE
            stack.append(())
        elif op == "d":     # DICT
            items = pop_mark()
            stack.append(dict(zip(items[0::2], items[1::2])))
        elif op == "l":     # LIST
            stack.append(pop_mark())
        elif op == "t":     # TUPLE
            stack.append(tuple(pop_mark()))
        elif op in "\x85\x86\x87":  # TUPLE1 / TUPLE2 / TUPLE3
            n = "\x85\x86\x87".index(op) + 1
            items = stack[-n:]
            del stack[-n:]
            stack.append(tuple(items))
        elif op == "s":     # SETITEM
            value = stack.pop()
            key = stack.pop()
            stack[-1][key] = value
        elif op == "u":     # SETITEMS
            items = pop_mark()
            for i in range(0, len(items), 2):
                stack[-1][items[i]] = items[i + 1]
        elif op == "a":     # APPEND
            value = stack.pop()
            stack[-1].append(value)
        elif op == "e":     # APPENDS
            items = pop_mark()  # take the items first, then the list under them
            stack[-1].extend(items)
        elif op == "N":
            stack.append(None)
        elif op == "\x88":
            stack.append(True)
        elif op == "\x89":
            stack.append(False)
        elif op == "K":     # BININT1
            stack.append(struct.unpack("<B", take(1))[0])
        elif op == "M":     # BININT2
            stack.append(struct.unpack("<H", take(2))[0])
        elif op == "J":     # BININT
            stack.append(struct.unpack("<i", take(4))[0])
        elif op == "\x8a":  # LONG1
            n = struct.unpack("<B", take(1))[0]
            raw = bytearray(take(n))
            value = 0
            for i, b in enumerate(raw):
                value |= b << (8 * i)
            if n and raw[-1] & 0x80:
                value -= 1 << (8 * n)
            stack.append(value)
        elif op == "I":     # INT (protocol 0)
            line = take_line()
            if line == b"00":
                stack.append(False)
            elif line == b"01":
                stack.append(True)
            else:
                stack.append(int(line))
        elif op == "L":     # LONG (protocol 0)
            stack.append(int(take_line().rstrip(b"L")))
        elif op == "F":     # FLOAT (protocol 0)
            stack.append(float(take_line()))
        elif op == "G":     # BINFLOAT
            stack.append(struct.unpack(">d", take(8))[0])
        elif op == "\x8c":  # SHORT_BINUNICODE
            stack.append(text(take(struct.unpack("<B", take(1))[0])))
        elif op == "X":     # BINUNICODE
            stack.append(text(take(struct.unpack("<I", take(4))[0])))
        elif op == "\x8d":  # BINUNICODE8
            stack.append(text(take(struct.unpack("<Q", take(8))[0])))
        elif op == "V":     # UNICODE (protocol 0)
            stack.append(take_line().decode("raw-unicode-escape"))
        elif op == "U":     # SHORT_BINSTRING
            stack.append(text(take(struct.unpack("<B", take(1))[0])))
        elif op == "T":     # BINSTRING
            stack.append(text(take(struct.unpack("<i", take(4))[0])))
        elif op == "S":     # STRING (protocol 0)
            raw = take_line().strip()
            stack.append(text(raw[1:-1]))
        elif op == "\x94":  # MEMOIZE
            memo[len(memo)] = stack[-1]
        elif op == "q":     # BINPUT
            memo[struct.unpack("<B", take(1))[0]] = stack[-1]
        elif op == "r":     # LONG_BINPUT
            memo[struct.unpack("<I", take(4))[0]] = stack[-1]
        elif op == "p":     # PUT
            memo[int(take_line())] = stack[-1]
        elif op == "h":     # BINGET
            stack.append(memo[struct.unpack("<B", take(1))[0]])
        elif op == "j":     # LONG_BINGET
            stack.append(memo[struct.unpack("<I", take(4))[0]])
        elif op == "g":     # GET
            stack.append(memo[int(take_line())])
        elif op == "0":     # POP
            stack.pop()
        else:
            raise ValueError("salary_model.pkl contains unsupported data (opcode %r)." % op)


class ModelError(Exception):
    """salary_model.pkl is missing or is not the Activity 1 model."""


WRONG_MODEL_HELP = (
    "Run  python train_model.py  to create it again from salary_dataset.csv.\n"
    "That file is a dictionary with 'coefficients' and 'education'.\n"
    "(A scikit-learn / joblib model, or a damaged download, cannot be used here.)"
)


def load_model(path=MODEL_PATH):
    if not os.path.exists(path):
        raise ModelError(
            "Saved model not found: %s\n"
            "Run  python train_model.py  first to train and save the model." % path
        )
    with open(path, "rb") as f:
        raw = f.read()
    try:
        data = pickle.loads(raw)
    except Exception:
        # Older Python that cannot read this pickle format -> built-in reader
        try:
            data = read_simple_pickle(raw)
        except Exception:
            raise ModelError("Cannot read %s.\n%s" % (path, WRONG_MODEL_HELP))
    if not isinstance(data, dict) or "coefficients" not in data or "education" not in data:
        raise ModelError("%s is not the Activity 1 model.\n%s" % (path, WRONG_MODEL_HELP))
    if len(data["coefficients"]) != 4:
        raise ModelError(
            "%s has %d coefficients; expected 4 (intercept, education, experience, hours)."
            % (path, len(data["coefficients"]))
        )
    return data


try:
    model = load_model()
except ModelError as err:
    print("")
    print("=" * 60)
    print(" SalaryScope could not start")
    print("=" * 60)
    print(" %s" % str(err).replace("\n", "\n "))
    print("=" * 60)
    sys.exit(1)
COEFFICIENTS = [float(c) for c in model["coefficients"]]
EDUCATION_CODES = dict((to_text(k), v) for k, v in model["education"].items())
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


def _open_csv(mode):
    if PY2:
        return open(HISTORY_PATH, mode + "b")
    return io.open(HISTORY_PATH, mode, newline="", encoding="utf-8")


def save_history(records):
    with _history_lock:
        new_file = not os.path.exists(HISTORY_PATH) or os.path.getsize(HISTORY_PATH) == 0
        f = _open_csv("a")
        try:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(HISTORY_FIELDS)
            for record in records:
                row = [to_text(record[k]) for k in HISTORY_FIELDS]
                if PY2:
                    row = [cell.encode("utf-8") for cell in row]
                writer.writerow(row)
        finally:
            f.close()


def read_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with _history_lock:
        f = _open_csv("r")
        try:
            rows = list(csv.reader(f))
        finally:
            f.close()
    if not rows:
        return []
    header = [to_text(h) for h in rows[0]]
    records = []
    for row in rows[1:]:
        r = OrderedDict(zip(header, [to_text(c) for c in row]))
        for key in ("years_experience", "working_hours", "predicted_salary"):
            try:
                value = float(r[key])
                r[key] = int(value) if value.is_integer() and key != "predicted_salary" else value
            except (KeyError, TypeError, ValueError):
                pass
        records.append(r)
    return records


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


def ordered(*pairs):
    result = OrderedDict()
    for key, value in pairs:
        result[key] = value
    return result


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
class ValidationError(Exception):
    def __init__(self, errors):
        Exception.__init__(self, "Invalid input")
        self.errors = errors


def _number(data, key, label, errors):
    raw = data.get(key)
    if raw is None or (isinstance(raw, string_types) and raw.strip() == ""):
        errors[key] = "%s is required." % label
        return None
    if isinstance(raw, bool):
        errors[key] = "%s must be a number." % label
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        errors[key] = "%s must be a number." % label
        return None
    if not is_finite(value):
        errors[key] = "%s must be a finite number." % label
        return None
    return int(value) if value.is_integer() else value


def validate_common(data, errors):
    name = to_text(data.get("employee_name") or "").strip()
    if not name:
        errors["employee_name"] = "Employee name must not be empty."

    education = to_text(data.get("education") or "").strip()
    if education not in EDUCATION_CODES:
        errors["education"] = "Education must be one of: " + ", ".join(EDUCATION_LEVELS) + "."

    hours = _number(data, "working_hours", "Working hours", errors)
    if hours is not None and not (MIN_HOURS <= hours <= MAX_HOURS):
        errors["working_hours"] = "Working hours must be between %d and %d per week." % (MIN_HOURS, MAX_HOURS)
    return name, education, hours


def validate_experience(data, key, label, errors):
    exp = _number(data, key, label, errors)
    if exp is not None and exp < 0:
        errors[key] = "%s must be 0 or greater." % label
    return exp


# --------------------------------------------------------------------------
# Endpoint handlers
# --------------------------------------------------------------------------
def handle_predict(data):
    errors = {}
    name, education, hours = validate_common(data, errors)
    # Activity 1 sends "experience"; the web page sends "years_experience". Both work.
    exp_key = "experience" if "experience" in data else "years_experience"
    exp = validate_experience(data, exp_key, "Years of experience", errors)
    if errors:
        raise ValidationError(errors)

    salary = predict_salary(education, exp, hours)
    record = make_record("predict", name, education, exp, hours, salary)
    save_history([record])
    # Same fields and order as the Activity 1 expected output, plus the
    # Activity 3 salary range and timestamp.
    return ordered(
        ("employee_name", name),
        ("experience", exp),
        ("education", education),
        ("working_hours", hours),
        ("predicted_salary", salary),
        ("currency", CURRENCY),
        ("salary_range", record["salary_range"]),
        ("timestamp", record["timestamp"]),
    )


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

    return ordered(
        ("employee_name", name),
        ("education", education),
        ("working_hours", hours),
        ("experience_1", exp1),
        ("experience_2", exp2),
        ("predicted_salary_1", salary1),
        ("predicted_salary_2", salary2),
        ("salary_difference", round(salary2 - salary1, 2)),
        ("salary_range_1", rec1["salary_range"]),
        ("salary_range_2", rec2["salary_range"]),
        ("currency", CURRENCY),
        ("comparison_id", comparison_id),
        ("timestamp", rec2["timestamp"]),
    )


def handle_history():
    records = read_history()
    records.reverse()  # newest first
    return ordered(("count", len(records)), ("currency", CURRENCY), ("records", records))


def handle_meta():
    return ordered(
        ("education_levels", EDUCATION_LEVELS),
        ("currency", CURRENCY),
        ("thresholds", ordered(
            ("LOW", "below " + money(LOW_LIMIT)),
            ("MEDIUM", money(LOW_LIMIT) + " to " + money(HIGH_LIMIT - 0.01, 2)),
            ("HIGH", money(HIGH_LIMIT) + " and above"),
        )),
        ("working_hours_range", [MIN_HOURS, MAX_HOURS]),
        ("training_records", model.get("training_records")),
    )


def render_index():
    default = "Bachelor's Degree" if "Bachelor's Degree" in EDUCATION_CODES else EDUCATION_LEVELS[0]
    chips = "\n".join(
        '<label class="chip"><input type="radio" name="education" value="%s"%s><span>%s</span></label>'
        % (html_escape(level), " checked" if level == default else "", html_escape(level))
        for level in EDUCATION_LEVELS
    )
    # HTML entities keep this file plain ASCII: &#8369; = peso sign
    footer = (
        "LOW &lt; &#8369;%s &middot; MEDIUM &#8369;%s&ndash;&#8369;%s &middot; HIGH &ge; &#8369;%s"
        % (money(LOW_LIMIT), money(LOW_LIMIT), money(HIGH_LIMIT - 0.01, 2), money(HIGH_LIMIT))
    )
    f = io.open(TEMPLATE_PATH, encoding="utf-8")
    try:
        page = f.read()
    finally:
        f.close()
    values = {
        "education_chips": chips,
        "footer_ranges": footer,
        "low_limit": LOW_LIMIT,
        "high_limit": HIGH_LIMIT,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
    }
    for key, value in values.items():
        page = page.replace("{{ " + key + " }}", to_text(value))
    return page


# --------------------------------------------------------------------------
# HTTP server (standard library only)
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SalaryScope/1.0"

    def _send(self, status, body, content_type="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=PY2, indent=2)
        if isinstance(body, text_type):
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
        ctype = self.headers.get("Content-Type") or ""
        if "application/json" in ctype:
            try:
                data = json.loads(raw or "{}")
            except ValueError:
                return None
            return data if isinstance(data, dict) else None
        return dict((to_text(k), to_text(v[0])) for k, v in parse_qs(raw).items())

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
            self._send(400, ordered(("error", "Invalid input."), ("details", err.errors)))

    def _serve_static(self, rel):
        full = os.path.realpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": "Not found."})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".js"):
            ctype = "application/javascript"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def log_message(self, fmt, *args):
        status = args[1] if len(args) > 1 else ""
        print("[%s] %s %s -> %s" % (datetime.now().strftime("%H:%M:%S"), self.command, self.path, status))


def create_server(host=HOST, port=PORT):
    return ThreadingHTTPServer((host, port), Handler)


def start_server(host=HOST, first_port=PORT, tries=10):
    """Start on the first free port (5000, 5001, ...) in case one is busy."""
    for port in range(first_port, first_port + tries):
        try:
            return create_server(host, port)
        except (OSError, IOError):
            print("Port %d is busy, trying %d..." % (port, port + 1))
    raise IOError("No free port found between %d and %d." % (first_port, first_port + tries - 1))


def open_browser(url):
    """Open the local page automatically. 127.0.0.1 is this computer, so no internet is needed."""
    try:
        webbrowser.open(url, new=2)
    except Exception:
        print("Could not open the browser automatically. Please open %s" % url)


if __name__ == "__main__":
    server = start_server()
    url = "http://%s:%d" % (HOST, server.server_address[1])

    print("=" * 60)
    print(" SalaryScope - Employee Salary Prediction System (OFFLINE)")
    print("=" * 60)
    print(" Python       : %s" % sys.version.split()[0])
    print(" Model loaded : %s" % MODEL_PATH)
    print(" Coefficients : %s" % COEFFICIENTS)
    print(" Education    : %s" % ", ".join(EDUCATION_LEVELS))
    print(" History file : %s" % HISTORY_PATH)
    print(" Running at   : %s" % url)
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
