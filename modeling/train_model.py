from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "drowsiness_samples.csv"
ARTIFACT_DIR = ROOT / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "drowsiness_model.joblib"

FEATURES = [
    "ear",
    "eye_closed_duration_ms",
    "face_pitch",
    "face_yaw",
    "face_roll",
]


def train() -> None:
    data = pd.read_csv(DATA_PATH)
    x = data[FEATURES]
    y = data["label"]

    stratify = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.25,
        random_state=42,
        stratify=stratify,
    )

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=150,
                    max_depth=5,
                    random_state=42,
                    class_weight="balanced",
                ),
            ),
        ]
    )
    model.fit(x_train.to_numpy(), y_train)

    predictions = model.predict(x_test.to_numpy())
    print(classification_report(y_test, predictions, target_names=["drowsy", "awake"]))

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
