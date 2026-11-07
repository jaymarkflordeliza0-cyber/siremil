"""
Backup: recreate salary_model.pkl from Laboratory Activity 1.

This does NOT retrain anything. It writes back the exact values that were
saved in the original Activity 1 model, producing a byte-for-byte identical
salary_model.pkl (MD5 BD39B857F0F96DDA2DB9F59F9C6733A0).

    python make_model.py
"""

import pickle

model = {
    "coefficients": [-929.6841927017103, 1898.4844636355951, 2901.4901363135996, 300.0],
    "education": {
        "High School": 0,
        "Associate Degree": 1,
        "Bachelor's Degree": 2,
        "Master's Degree": 3,
        "Doctorate": 4,
    },
    "training_records": 24,
}

with open("salary_model.pkl", "wb") as f:
    pickle.dump(model, f, protocol=4)

print("salary_model.pkl created")
