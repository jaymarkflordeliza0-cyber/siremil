# -*- coding: utf-8 -*-
"""
Laboratory Activity 1 - Employee Salary Prediction System
Model Persistence and Basic Deployment (Part 1)

System flow:
    Input Employee Training Dataset -> Train Prediction Model -> Save Model

    python train_model.py

Reads   salary_dataset.csv  (24 employee records)
Trains  a multiple linear regression model (least squares)
Saves   salary_model.pkl    using Pickle

Uses ONLY the Python standard library, so it runs offline on
Python 2.7 and every Python 3 version.
"""

from __future__ import division, print_function

import csv
import io
import os
import pickle
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "salary_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "salary_model.pkl")

# Education level -> number used by the model (higher = more education)
EDUCATION_CODES = {
    "High School": 0,
    "Associate Degree": 1,
    "Bachelor's Degree": 2,
    "Master's Degree": 3,
    "Doctorate": 4,
}


def load_dataset(path=DATASET_PATH):
    """Read the training records from the CSV file."""
    if sys.version_info[0] == 2:
        f = open(path, "rb")
    else:
        f = io.open(path, "r", newline="", encoding="utf-8")
    try:
        rows = list(csv.DictReader(f))
    finally:
        f.close()

    records = []
    for line_no, row in enumerate(rows, start=2):
        education = row["education"].strip()
        if education not in EDUCATION_CODES:
            raise ValueError("Line %d: unknown education level %r" % (line_no, education))
        records.append({
            "employee_name": row["employee_name"].strip(),
            "education": education,
            "years_experience": float(row["years_experience"]),
            "working_hours": float(row["working_hours"]),
            "monthly_salary": float(row["monthly_salary"]),
        })
    if len(records) < 20:
        raise ValueError("The dataset needs at least 20 employee records (found %d)." % len(records))
    return records


def features(record):
    """[1, education_code, years_experience, working_hours] - the 1 is for the intercept."""
    return [1.0, float(EDUCATION_CODES[record["education"]]),
            record["years_experience"], record["working_hours"]]


def solve(matrix, vector):
    """Solve matrix * x = vector with Gaussian elimination (partial pivoting)."""
    n = len(vector)
    a = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("The dataset does not have enough variety to train the model.")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))) / a[r][r]
    return x


def train(records):
    """
    Multiple linear regression using the normal equation:  (X^T X) b = X^T y
    salary = b0 + b1*education_code + b2*years_experience + b3*working_hours
    """
    X = [features(r) for r in records]
    y = [r["monthly_salary"] for r in records]
    k = len(X[0])
    xtx = [[sum(row[i] * row[j] for row in X) for j in range(k)] for i in range(k)]
    xty = [sum(row[i] * target for row, target in zip(X, y)) for i in range(k)]
    return solve(xtx, xty)


def predict(coefficients, education, years_experience, working_hours):
    b0, b_edu, b_exp, b_hours = coefficients
    return b0 + b_edu * EDUCATION_CODES[education] + b_exp * years_experience + b_hours * working_hours


def evaluate(coefficients, records):
    """R-squared and mean absolute error on the training records."""
    actual = [r["monthly_salary"] for r in records]
    predicted = [predict(coefficients, r["education"], r["years_experience"], r["working_hours"])
                 for r in records]
    mean = sum(actual) / len(actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    ss_tot = sum((a - mean) ** 2 for a in actual)
    mae = sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)
    return 1 - ss_res / ss_tot, mae


def save_model(coefficients, records, path=MODEL_PATH):
    model = {
        "coefficients": coefficients,          # [intercept, education, experience, hours]
        "education": dict(EDUCATION_CODES),
        "training_records": len(records),
    }
    with open(path, "wb") as f:
        pickle.dump(model, f, protocol=2)      # protocol 2 = readable by Python 2.7 and 3.x
    return model


def main():
    records = load_dataset()
    print("Loaded dataset : %s (%d records)" % (DATASET_PATH, len(records)))

    coefficients = train(records)
    r2, mae = evaluate(coefficients, records)

    print("")
    print("Trained model  : salary = %.2f + %.2f*education + %.2f*years + %.2f*hours"
          % tuple(coefficients))
    print("R-squared      : %.4f" % r2)
    print("Mean abs error : PHP %.2f" % mae)

    save_model(coefficients, records)
    print("")
    print("Model saved    : %s" % MODEL_PATH)
    print("Next step      : python app.py")


if __name__ == "__main__":
    main()
