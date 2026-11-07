"""
Laboratory Activity 1 — Train and save the Employee Salary Prediction model.

Run this ONCE to create `salary_model.pkl`. The web application (app.py)
never retrains — it only loads the saved model and uses it for predictions.

If you already have your own `salary_model.pkl` from Activity 1, you do not
need to run this file; just place your model next to app.py.

    python train_model.py
"""

import os

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "salary_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "salary_model.pkl")

FEATURES = ["education", "years_experience", "working_hours"]
TARGET = "monthly_salary"

# Typical monthly base pay (PHP) per education level used to build the
# training dataset. These are TRAINING data only — the app never uses them.
EDUCATION_BASE = {
    "High School": 11000,
    "Vocational": 13000,
    "Bachelor's Degree": 16000,
    "Master's Degree": 23000,
    "Doctorate": 32000,
}


def build_dataset(n_rows=600, seed=42):
    """Create a reproducible employee salary dataset (monthly, PHP)."""
    rng = np.random.default_rng(seed)
    education = rng.choice(list(EDUCATION_BASE), size=n_rows)
    experience = rng.integers(0, 31, size=n_rows)
    hours = rng.integers(20, 61, size=n_rows)
    noise = rng.normal(0, 1800, size=n_rows)

    salary = (
        np.array([EDUCATION_BASE[e] for e in education])
        + experience * 1500
        + (hours - 40) * 150
        + noise
    )
    return pd.DataFrame(
        {
            "education": education,
            "years_experience": experience,
            "working_hours": hours,
            TARGET: np.round(np.clip(salary, 8000, None), 2),
        }
    )


def main():
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        print(f"Loaded dataset: {DATA_PATH} ({len(df)} rows)")
    else:
        df = build_dataset()
        df.to_csv(DATA_PATH, index=False)
        print(f"Created dataset: {DATA_PATH} ({len(df)} rows)")

    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = Pipeline(
        steps=[
            (
                "preprocess",
                ColumnTransformer(
                    transformers=[
                        (
                            "education",
                            OneHotEncoder(handle_unknown="ignore"),
                            ["education"],
                        )
                    ],
                    remainder="passthrough",
                ),
            ),
            ("regressor", LinearRegression()),
        ]
    )
    pipeline.fit(X_train, y_train)

    preds = pipeline.predict(X_test)
    print(f"R^2 score : {r2_score(y_test, preds):.4f}")
    print(f"MAE (PHP) : {mean_absolute_error(y_test, preds):,.2f}")

    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved: {MODEL_PATH}")


if __name__ == "__main__":
    main()
