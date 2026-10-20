"""FaceService: checks a face photo and turns it into a face code.

Used for candidate identification (F7): the photo from the application form
becomes a face code at Fetch CVs, and the one photo taken when the candidate
joins is compared with it.

    photo -> YuNet finds faces -> exactly one, big, sharp, light enough
          -> SFace makes the face code (128 numbers)

Everything runs locally on the CPU. Nothing here is logged or saved; the
callers decide what is kept. The OpenCV models are not thread-safe, so
they are used one call at a time.
"""

import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.services import face_models

# Larger photos are made smaller first, so finding faces stays fast.
MAX_SIDE = 1280
# How sure YuNet must be before something counts as a face (0 to 1).
DETECTION_SCORE = 0.8
# A usable face: at least this many pixels wide, with some sharpness and
# light. Set from the face-match test (scripts/face_match_check.py): dim,
# far and slightly blurred faces still matched well above these values.
MIN_FACE_PX = 60
MIN_SHARPNESS = 5.0
MIN_BRIGHTNESS = 40.0
# A stored photo is made at most this big and saved as JPEG, which also
# drops the file's hidden details (camera, place, time).
STORED_SIDE = 800

# Match bands (SFace cosine similarity). 0.363 is SFace's published
# same-person limit. In the face-match test the same person scored 0.58 to
# 0.63 against a passport photo, and a different person 0.30.
VERIFIED = 0.50
LOW = 0.363

# Why a photo cannot be used, in words for the interviewer.
NOT_AN_IMAGE = "not_an_image"
NO_FACE = "no_face"
SEVERAL_FACES = "several_faces"
TOO_SMALL = "too_small"
TOO_BLURRY = "too_blurry"
TOO_DARK = "too_dark"
NOT_DOWNLOADED = "not_downloaded"
CHECK_FAILED = "check_failed"
PROBLEMS = {
    NOT_AN_IMAGE: "not a JPG or PNG photo",
    NO_FACE: "no face found",
    SEVERAL_FACES: "more than one face",
    TOO_SMALL: "face too small",
    TOO_BLURRY: "too blurry",
    TOO_DARK: "too dark",
    NOT_DOWNLOADED: "could not be downloaded",
    CHECK_FAILED: "could not be checked",
}

_lock = threading.Lock()


@dataclass(frozen=True)
class FaceCheck:
    """The result of checking one photo: the face code if it can be used,
    otherwise the reason it cannot. The image is kept only so the caller
    can store the photo; it is never written here."""

    code: bytes | None = None
    problem: str | None = None
    image: np.ndarray | None = None


@lru_cache
def _models(folder: str) -> tuple:
    paths = face_models.ensure_models(Path(folder))
    detector = cv2.FaceDetectorYN.create(
        str(paths[face_models.DETECTOR]), "", (320, 320), DETECTION_SCORE
    )
    recogniser = cv2.FaceRecognizerSF.create(str(paths[face_models.RECOGNISER]), "")
    return detector, recogniser


def _models_folder() -> str:
    from app.core.config import get_settings

    return get_settings().face_models_dir


def read_image(content: bytes) -> np.ndarray | None:
    """The photo as an image, turned the right way up, or None."""
    data = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if image is None:
        return None
    scale = MAX_SIDE / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return image


def quality_problem(image: np.ndarray, face: np.ndarray) -> str | None:
    """Why this face is not good enough for a face code, or None."""
    x, y, width, height = (int(value) for value in face[:4])
    if width < MIN_FACE_PX:
        return TOO_SMALL
    crop = image[max(y, 0) : y + height, max(x, 0) : x + width]
    if crop.size == 0:
        return NO_FACE
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if float(grey.mean()) < MIN_BRIGHTNESS:
        return TOO_DARK
    if cv2.Laplacian(grey, cv2.CV_64F).var() < MIN_SHARPNESS:
        return TOO_BLURRY
    return None


def check_photo(content: bytes, models_folder: str | None = None) -> FaceCheck:
    """Check a photo and make its face code. Exactly one face must be found,
    and it must be big, sharp and light enough."""
    image = read_image(content)
    if image is None:
        return FaceCheck(problem=NOT_AN_IMAGE)
    with _lock:
        detector, recogniser = _models(models_folder or _models_folder())
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        faces = faces if faces is not None else np.empty((0, 15))
        if len(faces) == 0:
            return FaceCheck(problem=NO_FACE, image=image)
        if len(faces) > 1:
            return FaceCheck(problem=SEVERAL_FACES, image=image)
        problem = quality_problem(image, faces[0])
        if problem:
            return FaceCheck(problem=problem, image=image)
        aligned = recogniser.alignCrop(image, faces[0])
        feature = recogniser.feature(aligned).astype(np.float32).reshape(-1)
    return FaceCheck(code=feature.tobytes(), image=image)


def similarity(code_a: bytes, code_b: bytes) -> float:
    """How alike two face codes are: SFace's cosine similarity, -1 to 1."""
    a = np.frombuffer(code_a, dtype=np.float32)
    b = np.frombuffer(code_b, dtype=np.float32)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def band(score: float) -> str:
    """verified, low or very_low for a match score."""
    if score >= VERIFIED:
        return "verified"
    if score >= LOW:
        return "low"
    return "very_low"


def jpeg_for_storage(image: np.ndarray) -> bytes:
    """The photo as a JPEG of at most STORED_SIDE pixels, without the
    original file's hidden details."""
    scale = STORED_SIDE / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise ValueError("The photo could not be saved.")
    return data.tobytes()
