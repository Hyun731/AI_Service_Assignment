from pathlib import Path

import joblib
import numpy as np


FEATURE_ORDER = [
    "ear",
    "eye_closed_duration_ms",
    "face_pitch",
    "face_yaw",
    "face_roll",
]

MODEL_PATH = Path(__file__).resolve().parents[2] / "modeling" / "artifacts" / "drowsiness_model.joblib"


class DrowsinessPredictor:
    def __init__(self) -> None:
        self.model = None
        self.load_model()

    def load_model(self) -> None:
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)

    def predict(self, features: dict[str, float]) -> tuple[bool, float]:
        heuristic_is_drowsy, heuristic_probability = self._heuristic_predict(features)
        if heuristic_is_drowsy:
            return heuristic_is_drowsy, heuristic_probability

        row = np.array([[features[name] for name in FEATURE_ORDER]], dtype=float)
        if self.model is None:
            return heuristic_is_drowsy, heuristic_probability

        prediction = int(self.model.predict(row)[0])
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(row)[0]
            class_index = list(self.model.classes_).index(prediction)
            probability = float(probabilities[class_index])
        else:
            probability = 0.8
        return prediction == 0, probability

    @staticmethod
    def _heuristic_predict(features: dict[str, float]) -> tuple[bool, float]:
        ear = features["ear"]
        closed_ms = features["eye_closed_duration_ms"]
        head_tilt = abs(features["face_pitch"]) + abs(features["face_roll"]) * 0.6
        score = 0
        if ear < 0.2:
            score += 0.55
        elif ear < 0.24:
            score += 0.35
        if closed_ms > 1200:
            score += 0.35
        elif closed_ms > 700:
            score += 0.2
        if head_tilt > 18:
            score += 0.15
        probability = min(0.98, max(0.05, score))
        return probability >= 0.5, probability


predictor = DrowsinessPredictor()
