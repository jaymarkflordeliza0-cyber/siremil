"""
Automated checks for Activity 3 (steps 8-10).

    python -m unittest test_app -v

Uses a temporary history file so your real salary_history.csv is untouched.
"""

import csv
import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def get_json(self):
        return json.loads(self._body)


class Client:
    """Tiny HTTP client that talks to a real running server on a free port."""

    def __init__(self, module):
        self.server = module.create_server(port=0)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _open(self, req):
        try:
            with urllib.request.urlopen(req) as r:
                return Response(r.status, r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return Response(e.code, e.read().decode("utf-8"))

    def get(self, path):
        return self._open(self.base + path)

    def post(self, path, json=None):
        req = urllib.request.Request(
            self.base + path, data=_dumps(json).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        return self._open(req)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


_dumps = json.dumps


def load_app(history_path):
    """(Re)import app.py from scratch — simulates restarting the application."""
    os.environ["SALARY_HISTORY_PATH"] = history_path
    sys.modules.pop("app", None)
    return importlib.import_module("app")


class SalaryAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = os.path.join(self.tmp.name, "salary_history.csv")
        self.app = load_app(self.history)
        self.client = Client(self.app)
        self.edu = self.app.EDUCATION_LEVELS

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()
        os.environ.pop("SALARY_HISTORY_PATH", None)

    def rows(self):
        with open(self.history, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

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
            r = self.client.post("/predict", json={
                "employee_name": name, "education": edu,
                "years_experience": exp, "working_hours": hrs})
            self.assertEqual(r.status_code, 200, r.get_json())
            body = r.get_json()
            expected = self.app.predict_salary(edu, exp, hrs)  # straight from the model
            self.assertEqual(body["predicted_salary"], expected)
            self.assertEqual(body["salary_range"], self.app.classify_salary(expected))
            self.assertEqual(body["currency"], "PHP")
            print(f"  predict  {name:16} -> PHP {body['predicted_salary']:>12,.2f}  {body['salary_range']}")
        self.assertEqual(len(self.rows()), 5)

    # ---------------- Step 9: two comparison scenarios ----------------
    def test_two_comparisons(self):
        scenarios = [
            ("Juan Dela Cruz", "Bachelor's Degree", 48, 3, 5),
            ("Maria Santos", "Master's Degree", 40, 2, 10),
        ]
        for name, edu, hrs, e1, e2 in scenarios:
            r = self.client.post("/compare", json={
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
            print(f"  compare  {name:16} -> diff PHP {b['salary_difference']:>10,.2f}")
        rows = self.rows()
        self.assertEqual(len(rows), 4)  # each comparison saves both predictions
        self.assertTrue(all(r["request_type"] == "compare" for r in rows))
        self.assertEqual(rows[0]["comparison_id"], rows[1]["comparison_id"])

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
            r = self.client.post("/predict", json={**good, **patch})
            self.assertEqual(r.status_code, 400)
            self.assertIn(field, r.get_json()["details"])
        r = self.client.post("/compare", json={
            "employee_name": "Juan", "education": self.edu[0], "working_hours": 40,
            "experience_1": 3, "experience_2": 3})
        self.assertEqual(r.status_code, 400)
        # failed requests are NOT saved
        self.assertFalse(os.path.exists(self.history))

    # ---------------- Step 10: restart and verify ----------------
    def test_restart_keeps_history_and_model(self):
        self.client.post("/predict", json={"employee_name": "Juan", "education": self.edu[0],
                                           "years_experience": 2, "working_hours": 40})
        app2 = load_app(self.history)  # "restart"
        client2 = Client(app2)
        self.addCleanup(client2.close)
        self.assertEqual(client2.get("/history").get_json()["count"], 1)
        r = client2.post("/compare", json={"employee_name": "Juan", "education": self.edu[0],
                                           "working_hours": 40, "experience_1": 1, "experience_2": 4})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(client2.get("/history").get_json()["count"], 3)
        self.assertEqual(client2.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
