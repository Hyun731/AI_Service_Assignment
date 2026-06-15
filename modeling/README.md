# Modeling

This folder trains and exports the drowsiness classifier used by the FastAPI backend.

The sample CSV is intentionally small so the project can run immediately. Replace
`data/drowsiness_samples.csv` with labeled webcam feature rows for better results.

## Train

```bash
pip install -r requirements.txt
python train_model.py
```

The exported model is written to `artifacts/drowsiness_model.joblib`.
