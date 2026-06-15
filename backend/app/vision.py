import base64
from dataclasses import dataclass

import numpy as np


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


@dataclass
class FaceFeatures:
    ear: float
    face_pitch: float
    face_yaw: float
    face_roll: float
    face_box: dict[str, int] | None = None
    eye_boxes: list[dict[str, int]] | None = None


def decode_base64_image(image_base64: str) -> np.ndarray:
    import cv2

    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]
    image_bytes = base64.b64decode(image_base64)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Invalid image frame")
    return frame


def eye_aspect_ratio(points: np.ndarray) -> float:
    vertical_1 = np.linalg.norm(points[1] - points[5])
    vertical_2 = np.linalg.norm(points[2] - points[4])
    horizontal = np.linalg.norm(points[0] - points[3])
    if horizontal == 0:
        return 0.0
    return float((vertical_1 + vertical_2) / (2.0 * horizontal))


def extract_face_features(frame: np.ndarray) -> FaceFeatures:
    import cv2
    import mediapipe as mp

    if not hasattr(mp, "solutions"):
        return extract_face_features_with_opencv(frame)

    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    )
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = mesh.process(rgb)
    mesh.close()

    if not result.multi_face_landmarks:
        raise ValueError("No face detected")

    height, width = frame.shape[:2]
    landmarks = result.multi_face_landmarks[0].landmark
    points = np.array([[lm.x * width, lm.y * height, lm.z * width] for lm in landmarks])
    min_x = int(np.clip(np.min(points[:, 0]), 0, width))
    min_y = int(np.clip(np.min(points[:, 1]), 0, height))
    max_x = int(np.clip(np.max(points[:, 0]), 0, width))
    max_y = int(np.clip(np.max(points[:, 1]), 0, height))

    left_ear = eye_aspect_ratio(points[LEFT_EYE, :2])
    right_ear = eye_aspect_ratio(points[RIGHT_EYE, :2])
    ear = float((left_ear + right_ear) / 2.0)
    left_eye_box = landmarks_to_box(points[LEFT_EYE, :2], width, height, padding=8)
    right_eye_box = landmarks_to_box(points[RIGHT_EYE, :2], width, height, padding=8)

    nose = points[1]
    chin = points[152]
    left_face = points[234]
    right_face = points[454]
    eye_left = points[33]
    eye_right = points[263]

    face_yaw = float((nose[0] - ((left_face[0] + right_face[0]) / 2)) / max(1, width) * 100)
    face_pitch = float((nose[1] - ((eye_left[1] + eye_right[1]) / 2)) / max(1, height) * 100)
    face_roll = float(np.degrees(np.arctan2(eye_right[1] - eye_left[1], eye_right[0] - eye_left[0])))

    if chin[1] < nose[1]:
        face_pitch *= -1

    return FaceFeatures(
        ear=ear,
        face_pitch=face_pitch,
        face_yaw=face_yaw,
        face_roll=face_roll,
        face_box={"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y},
        eye_boxes=[left_eye_box, right_eye_box],
    )


def extract_face_features_with_opencv(frame: np.ndarray) -> FaceFeatures:
    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        raise ValueError("No face detected")

    x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
    face_gray = gray[y : y + h, x : x + w]
    upper_face = face_gray[: max(1, int(h * 0.62)), :]
    eyes = eye_cascade.detectMultiScale(
        upper_face,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(18, 18),
    )

    expected_eye_regions = get_expected_eye_regions(face_gray)
    openness_scores = [
        estimate_eye_openness(region)
        for region in expected_eye_regions
        if region.size > 0
    ]
    average_openness = float(np.mean(openness_scores)) if openness_scores else 0.0
    ear = float(np.clip(0.12 + (average_openness * 0.24), 0.12, 0.36))

    frame_h, frame_w = frame.shape[:2]
    face_center_x = x + (w / 2)
    face_center_y = y + (h / 2)
    face_yaw = float((face_center_x - (frame_w / 2)) / max(1, frame_w) * 35)
    face_pitch = float((face_center_y - (frame_h / 2)) / max(1, frame_h) * 35)

    return FaceFeatures(
        ear=ear,
        face_pitch=face_pitch,
        face_yaw=face_yaw,
        face_roll=0.0,
        face_box={"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
        eye_boxes=get_expected_eye_boxes(x, y, w, h),
    )


def landmarks_to_box(
    points: np.ndarray,
    frame_width: int,
    frame_height: int,
    padding: int = 0,
) -> dict[str, int]:
    min_x = int(np.clip(np.min(points[:, 0]) - padding, 0, frame_width))
    min_y = int(np.clip(np.min(points[:, 1]) - padding, 0, frame_height))
    max_x = int(np.clip(np.max(points[:, 0]) + padding, 0, frame_width))
    max_y = int(np.clip(np.max(points[:, 1]) + padding, 0, frame_height))
    return {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y}


def estimate_eye_openness(eye_roi: np.ndarray) -> float:
    import cv2

    if eye_roi.size == 0:
        return 0.0

    resized = cv2.resize(eye_roi, (120, 60))
    equalized = cv2.equalizeHist(resized)
    blurred = cv2.GaussianBlur(equalized, (5, 5), 0)

    threshold = np.percentile(blurred, 32)
    dark_mask = np.where(blurred <= threshold, 255, 0).astype(np.uint8)
    dark_mask[:8, :] = 0
    dark_mask[-4:, :] = 0
    kernel = np.ones((2, 2), np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    large_contours = [contour for contour in contours if cv2.contourArea(contour) >= 8]
    if not large_contours:
        return 0.0

    combined = np.vstack(large_contours)
    _, _, dark_w, dark_h = cv2.boundingRect(combined)
    ys, xs = np.where(dark_mask > 0)
    if len(ys) == 0:
        return 0.0

    vertical_spread = float(np.std(ys) / dark_mask.shape[0])
    vertical_ratio = dark_h / dark_mask.shape[0]
    horizontal_ratio = dark_w / dark_mask.shape[1]
    dark_ratio = len(ys) / dark_mask.size

    line_like_penalty = 0.35 if horizontal_ratio > 0.45 and vertical_ratio < 0.18 else 0.0
    openness = (vertical_ratio * 0.55) + (vertical_spread * 1.2) + (dark_ratio * 0.25) - line_like_penalty

    return float(np.clip(openness, 0.0, 1.0))


def get_expected_eye_regions(face_gray: np.ndarray) -> list[np.ndarray]:
    left_region = face_gray[
        int(face_gray.shape[0] * 0.24) : int(face_gray.shape[0] * 0.48),
        int(face_gray.shape[1] * 0.15) : int(face_gray.shape[1] * 0.47),
    ]
    right_region = face_gray[
        int(face_gray.shape[0] * 0.24) : int(face_gray.shape[0] * 0.48),
        int(face_gray.shape[1] * 0.53) : int(face_gray.shape[1] * 0.85),
    ]
    return [left_region, right_region]


def get_expected_eye_boxes(face_x: int, face_y: int, face_w: int, face_h: int) -> list[dict[str, int]]:
    return [
        {
            "x": int(face_x + (face_w * 0.15)),
            "y": int(face_y + (face_h * 0.24)),
            "width": int(face_w * 0.32),
            "height": int(face_h * 0.24),
        },
        {
            "x": int(face_x + (face_w * 0.53)),
            "y": int(face_y + (face_h * 0.24)),
            "width": int(face_w * 0.32),
            "height": int(face_h * 0.24),
        },
    ]
