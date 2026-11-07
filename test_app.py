# -*- coding: utf-8 -*-
"""
Automated checks for Activity 3 (steps 8-10). Works on Python 2.7 and 3.x.

    python -m unittest test_app -v

Uses a temporary history file so your real salary_history.csv is untouched.
"""

from __future__ import print_function

import csv
import io
import json
import os
import pickle
import shutil
import sys
import tempfile
import threading
import unittest

try:  # Python 3
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
except ImportError:  # Python 2
    from urllib2 import Request, urlopen, HTTPError

try:
    from importlib import import_module
except ImportError:
    import_module = __import__


class Response(object):
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def get_json(self):
        return json.loads(self._body)


class Client(object):
    """Tiny HTTP client that talks to a real running server on a free port."""

    def __init__(self, module):
        self.server = module.create_server(port=0)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        t = threading.Thread(target=self.server.serve_forever)
        t.daemon = True
        t.start()

    def _open(self, req):
        try:
            r = urlopen(req)
            try:
                return Response(r.getcode(), r.read().decode("utf-8"))
            finally:
                r.close()
        except HTTPError as e:
            return Response(e.code, e.read().decode("utf-8"))

    def get(self, path):
        return self._open(self.base + path)

    def post(self, path, json_body=None):
        req = Request(
            self.base + path,
            data=json.dumps(json_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return self._open(req)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def load_app(history_path):
    """(Re)import app.py from scratch - simulates restarting the application."""
    os.environ["SALARY_HISTORY_PATH"] = history_path
    sys.modules.pop("app", None)
    return import_module("app")


class SalaryAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.history = os.path.join(self.tmp, "salary_history.csv")
        self.app = load_app(self.history)
        self.app.Handler.log_message = lambda *a: None  # keep test output clean
        self.client = Client(self.app)
        self.edu = self.app.EDUCATION_LEVELS

    def tearDown(self):
        self.client.close()
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("SALARY_HISTORY_PATH", None)

    def rows(self):
        return self.app.read_history()

    # ---------------- Step 9: five predictions ----------------
    def test_five_predictions(self):
        cases = [
            ("Juan Dela Cruz", "Bachelor's Degree", 3, 48),
            ("Maria Santos", "Master's Degree", 8, 40),
            ("Pedro Reyes", "High School", 0, 40),
            ("Ana Lopez", "Doctorate", 15, 45),
            ("Jose Garcia", "Associate Degree", 5, 60),
        ]
        for name, edu, exp, hrs in cases:
            r = self.client.post("/predict", {
                "employee_name": name, "education": edu,
                "years_experience": exp, "working_hours": hrs})
            self.assertEqual(r.status_code, 200, r.get_json())
            body = r.get_json()
            expected = self.app.predict_salary(edu, exp, hrs)  # straight from the model
            self.assertEqual(body["predicted_salary"], expected)
            self.assertEqual(body["salary_range"], self.app.classify_salary(expected))
            self.assertEqual(body["currency"], "PHP")
            print("  predict  %-16s -> PHP %12s  %s"
                  % (name, self.app.money(body["predicted_salary"], 2), body["salary_range"]))
        self.assertEqual(len(self.rows()), 5)

    # ---------------- Step 9: two comparison scenarios ----------------
    def test_two_comparisons(self):
        scenarios = [
            ("Juan Dela Cruz", "Bachelor's Degree", 48, 3, 5),
            ("Maria Santos", "Master's Degree", 40, 2, 10),
        ]
        for name, edu, hrs, e1, e2 in scenarios:
            r = self.client.post("/compare", {
                "employee_name": name, "education": edu, "working_hours": hrs,
                "experience_1": e1, "experience_2": e2})
            self.assertEqual(r.status_code, 200, r.get_json())
            b = r.get_json()
            for key in ("employee_name", "education", "working_hours", "experience_1",
                        "experience_2", "predicted_salary_1", "predicted_salary_2",
                        "salary_difference", "salary_range_2", "currency"):
                self.assertIn(key, b)
            self.assertEqual(b["predicted_salary_1"], self.app.predict_salary(edu, e1, hrs))
            self.assertEqual(b["predicted_salary_2"], self.app.predict_salary(edu, e2, hrs))
            self.assertAlmostEqual(
                b["salary_difference"], b["predicted_salary_2"] - b["predicted_salary_1"], places=2)
            print("  compare  %-16s -> diff PHP %10s" % (name, self.app.money(b["salary_difference"], 2)))
        rows = self.rows()
        self.assertEqual(len(rows), 4)  # each comparison saves both predictions
        self.assertTrue(all(r["request_type"] == "compare" for r in rows))
        self.assertEqual(rows[0]["comparison_id"], rows[1]["comparison_id"])

    # ---------------- Non-English names are saved correctly ----------------
    def test_unicode_name(self):
        name = u"José Peña"
        r = self.client.post("/predict", {"employee_name": name, "education": self.edu[0],
                                          "years_experience": 1, "working_hours": 40})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["employee_name"], name)
        self.assertEqual(self.rows()[0]["employee_name"], name)

    # ---------------- Step 5: classification thresholds ----------------
    def test_classification(self):
        c = self.app.classify_salary
        self.assertEqual(c(19999.99), "LOW")
        self.assertEqual(c(20000), "MEDIUM")
        self.assertEqual(c(49999.99), "MEDIUM")
        self.assertEqual(c(50000), "HIGH")

    # ---------------- Step 8: validation ----------------
    def test_validation(self):
        good = {"employee_name": "Juan", "education": self.edu[0],
                "years_experience": 1, "working_hours": 40}
        bad_cases = [
            ({"employee_name": "   "}, "employee_name"),
            ({"years_experience": -1}, "years_experience"),
            ({"years_experience": "abc"}, "years_experience"),
            ({"working_hours": 0}, "working_hours"),
            ({"working_hours": 169}, "working_hours"),
            ({"education": "Kindergarten"}, "education"),
        ]
        for patch, field in bad_cases:
            body = dict(good)
            body.update(patch)
            r = self.client.post("/predict", body)
            self.assertEqual(r.status_code, 400)
            self.assertIn(field, r.get_json()["details"])
        r = self.client.post("/compare", {
            "employee_name": "Juan", "education": self.edu[0], "working_hours": 40,
            "experience_1": 3, "experience_2": 3})
        self.assertEqual(r.status_code, 400)
        # failed requests are NOT saved
        self.assertFalse(os.path.exists(self.history))

    # ---------------- Step 10: restart and verify ----------------
    def test_restart_keeps_history_and_model(self):
        self.client.post("/predict", {"employee_name": "Juan", "education": self.edu[0],
                                      "years_experience": 2, "working_hours": 40})
        app2 = load_app(self.history)  # "restart"
        app2.Handler.log_message = lambda *a: None
        client2 = Client(app2)
        self.addCleanup(client2.close)
        self.assertEqual(client2.get("/history").get_json()["count"], 1)
        r = client2.post("/compare", {"employee_name": "Juan", "education": self.edu[0],
                                      "working_hours": 40, "experience_1": 1, "experience_2": 4})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(client2.get("/history").get_json()["count"], 3)
        self.assertEqual(client2.get("/").status_code, 200)

    # ---------------- Model file can be read on old Python versions ----------------
    def test_builtin_pickle_reader_matches_pickle(self):
        with open(self.app.MODEL_PATH, "rb") as f:
            raw = f.read()
        self.assertEqual(self.app.read_simple_pickle(raw), self.app.model)
        sample = {"coefficients": [-929.68, 1898.48, 2901.49, 300.0, -5, 70000, 2 ** 40],
                  "education": {"High School": 0, "Doctorate": 4},
                  "flags": (True, False, None), "training_records": 24}
        for protocol in range(0, pickle.HIGHEST_PROTOCOL + 1):
            data = pickle.dumps(sample, protocol)
            self.assertEqual(self.app.read_simple_pickle(data), sample, "protocol %d" % protocol)

    # ---------------- Wrong model file gives a clear message ----------------
    def test_wrong_model_file_is_reported(self):
        for content in (b"not a pickle at all", pickle.dumps([1, 2, 3], 2)):
            bad = os.path.join(self.tmp, "bad_model.pkl")
            with open(bad, "wb") as f:
                f.write(content)
            try:
                self.app.load_model(bad)
            except self.app.ModelError as err:
                self.assertIn("Activity 1", str(err))
            else:
                self.fail("ModelError was not raised")


if __name__ == "__main__":
    unittest.main(verbosity=2)
