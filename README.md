# SalaryScope — Employee Salary Prediction System

**Activity 3: Salary Comparison and Prediction History.** A Flask app that runs entirely offline. Every salary it shows comes from the saved `salary_model.pkl`.

## Features
| Feature | Where |
|---|---|
| Salary prediction (kept from Activity 1) | `POST /predict` · **Predict** tab |
| Salary scenario comparison: same education and hours, two experience values, plus the difference | `POST /compare` · **Compare** tab |
| Salary range classification: **LOW** < ₱20,000 · **MEDIUM** ₱20,000–₱49,999.99 · **HIGH** ≥ ₱50,000 | every response |
| Local prediction history saved to `salary_history.csv` with a timestamp. A comparison saves both predictions | `GET /history` · **History** tab |
| Input validation: name not empty, experience ≥ 0, hours 1–168, education must be one the model was trained on | server and browser |

UI extras: light and dark mode, animated results, a salary-range meter, a comparison chart, a highlighted JSON output with a Copy button, history search and filters, summary stats, CSV download, and a mobile layout. There are no CDNs or web fonts, so everything works without internet.

## Run
```bash
pip install -r requirements.txt        # only if not installed yet
python app.py                          # open http://127.0.0.1:5000
```
> **Using your own Activity 1 model?** Put your `salary_model.pkl` next to `app.py`. The app reads the supported education levels directly from the model. If you don't have one, run `python train_model.py` **once** to create it. The app itself never retrains.

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
`app.py` (server) · `train_model.py` (Activity 1 training, run once) · `salary_model.pkl` (saved model) · `salary_data.csv` (training data) · `templates/` + `static/` (UI) · `test_app.py` · `salary_history.csv` (created automatically)
