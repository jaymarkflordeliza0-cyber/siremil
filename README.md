# SalaryScope — Employee Salary Prediction System

**Activity 3: Salary Comparison and Prediction History.** It runs entirely offline and uses **only the Python standard library**, so there is nothing to install. Every salary it shows comes from the Activity 1 model, `salary_model.pkl`.

## The saved model (from Activity 1)
`salary_model.pkl` is a dictionary with `coefficients` = `[intercept, education, experience, hours]`, an `education` code map (High School=0 … Doctorate=4), and `training_records`. The app computes:

```
salary = intercept + b_edu × education_code + b_exp × years_experience + b_hours × working_hours
```
The education levels are read from the model and used for validation. The model is never retrained.

## Features
| Feature | Where |
|---|---|
| Salary prediction (kept from Activity 1) | `POST /predict` · **Predict** tab |
| Salary scenario comparison: same education and hours, two experience values, plus the difference | `POST /compare` · **Compare** tab |
| Salary range classification: **LOW** < ₱20,000 · **MEDIUM** ₱20,000–₱49,999.99 · **HIGH** ≥ ₱50,000 | every response |
| Local prediction history saved to `salary_history.csv` with a timestamp. A comparison saves both predictions | `GET /history` · **History** tab |
| Input validation: name not empty, experience ≥ 0, hours 1–168, education must be one the model was trained on | server and browser |

UI extras: light and dark mode, animated results, a salary-range meter, a comparison chart, a highlighted JSON output with a Copy button, history search and filters, summary stats, CSV download, and a mobile layout. There are no CDNs or web fonts, so everything works without internet.

## Requirements
**Python 3.6 or newer** on Windows, macOS or Linux. Nothing else to install. Tested on Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14. Python 2 is not supported.

## Run
```bash
python app.py            # starts the server AND opens the browser automatically
python app.py --no-browser   # server only
```
On Windows you can also just **double-click `run_app.bat`**. If port 5000 is busy, the app uses the next free port (5001, 5002, ...). Everything runs on `127.0.0.1` (this computer), so no internet is needed.

## API examples
```bash
curl -X POST http://127.0.0.1:5000/predict -H "Content-Type: application/json" \
  -d '{"employee_name":"Juan Dela Cruz","education":"Bachelor'"'"'s Degree","years_experience":3,"working_hours":48}'

curl -X POST http://127.0.0.1:5000/compare -H "Content-Type: application/json" \
  -d '{"employee_name":"Juan Dela Cruz","education":"Bachelor'"'"'s Degree","working_hours":48,"experience_1":3,"experience_2":5}'

curl http://127.0.0.1:5000/history              # JSON, newest first
curl http://127.0.0.1:5000/history?format=csv   # raw CSV
```

## Tests (steps 9–10)
```bash
python -m unittest test_app -v
```
The tests cover 5 predictions, 2 comparisons, the classification thresholds, validation, and a simulated restart. They write to a temporary history file, so your real `salary_history.csv` is not changed.

## Files
`app.py` (server) · `run_app.bat` (double-click launcher) · `salary_model.pkl` (Activity 1 saved model) · `templates/` + `static/` (UI) · `test_app.py` · `salary_history.csv` (created automatically)
