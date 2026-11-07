# SalaryScope — Employee Salary Prediction System

**Activity 3: Salary Comparison and Prediction History.** It runs entirely offline and uses **only the Python standard library**, so there is nothing to install. Every salary it shows comes from the Activity 1 model, `salary_model.pkl`.

## Activity 1: dataset, training and saved model
| File | What it is |
|---|---|
| `salary_dataset.csv` | Training dataset with 24 employee records (experience, education, weekly hours, monthly salary) |
| `train_model.py` | Trains a multiple linear regression (least squares, pure Python) and saves `salary_model.pkl` with Pickle |
| `salary_model.pkl` | The saved model: `coefficients` = `[intercept, education, experience, hours]`, an `education` code map (High School=0 to Doctorate=4), and `training_records` |

```bash
python train_model.py     # run once: dataset -> train -> salary_model.pkl
python app.py             # loads the saved model (no retraining) and opens the browser
```
The app computes:
```
salary = intercept + b_edu * education_code + b_exp * years_experience + b_hours * working_hours
```
`/predict` accepts `experience` (Activity 1) or `years_experience` (web page) and returns the Activity 1 fields in order: `employee_name`, `experience`, `education`, `working_hours`, `predicted_salary`, `currency`, plus `salary_range` and `timestamp`.

## Features
| Feature | Where |
|---|---|
| Salary prediction (kept from Activity 1) | `POST /predict` · **Predict** tab |
| Salary scenario comparison: same education and hours, two experience values, plus the difference | `POST /compare` · **Compare** tab |
| Salary range classification: **LOW** < ₱20,000 · **MEDIUM** ₱20,000–₱49,999.99 · **HIGH** ≥ ₱50,000 | every response |
| Local prediction history saved to `salary_history.csv` with a timestamp. A comparison saves both predictions | `GET /history` · **History** tab |
| Input validation: name not empty, experience ≥ 0, hours 1–168, education must be one the model was trained on | server and browser |

UI extras: light and dark mode, animated results, a salary-range meter, a comparison chart, a highlighted JSON output with a Copy button, history search and filters, summary stats, CSV download, and a mobile layout. There are no CDNs or web fonts, so everything works without internet.

## Requirements (works on other PCs)
| Part | Works on |
|---|---|
| Python (`app.py`, `train_model.py`) | **Python 2.7 and every Python 3.** Nothing to install (standard library only). Tests pass on 3.8 to 3.14; 2.7 and 3.0 to 3.7 were checked with a static analyzer (vermin), not run. |
| JavaScript (`static/js/app.js`) | Written in classic **ES5** JavaScript (no arrow functions, `let`/`const`, template strings, `async`/`await` or `fetch`), checked with the acorn parser, so it runs in old and new browsers. |
| CSS (`static/css/style.css`) | Has fallbacks for older browsers (`inset`, `place-items`, `clamp()`). Internet Explorer is not supported, because it lacks CSS variables. |
| Internet | Not needed. Everything runs on this computer (`127.0.0.1`). |

To use it on another PC, copy the whole folder and run `python app.py` (or double-click `run_app.bat` on Windows).

## Run
```bash
python app.py            # starts the server AND opens the browser automatically
python app.py --no-browser   # server only
```
On Windows you can also just **double-click `run_app.bat`**. If port 5000 is busy, the app uses the next free port (5001, 5002, ...). Everything runs on `127.0.0.1` (this computer), so no internet is needed.

## API examples
```bash
curl -X POST http://127.0.0.1:5000/predict -H "Content-Type: application/json" \
  -d '{"employee_name":"Juan Dela Cruz","experience":5,"education":"Bachelor'"'"'s Degree","working_hours":40}'

curl -X POST http://127.0.0.1:5000/compare -H "Content-Type: application/json" \
  -d '{"employee_name":"Juan Dela Cruz","education":"Bachelor'"'"'s Degree","working_hours":48,"experience_1":3,"experience_2":5}'

curl http://127.0.0.1:5000/history              # JSON, newest first
curl http://127.0.0.1:5000/history?format=csv   # raw CSV
```

## Tests (steps 9–10)
```bash
python -m unittest test_app -v
```
(The tests need Python 2.7 or 3.3+.)
The tests cover 5 predictions, 2 comparisons, the classification thresholds, validation, and a simulated restart. They write to a temporary history file, so your real `salary_history.csv` is not changed.

## Files
`app.py` (server) · `run_app.bat` (double-click launcher) · `train_model.py` + `salary_dataset.csv` (Activity 1) · `salary_model.pkl` (saved model) · `templates/` + `static/` (UI) · `test_app.py` · `salary_history.csv` (created automatically)
