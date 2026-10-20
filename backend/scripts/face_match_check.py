"""Test face matching before building candidate identification (F7).

Compares one enrolment photo (a passport-size photo, as in the Google Form)
with a few test photos (webcam snapshots in different conditions, and one
photo of another person) and prints how well each one matches.

Run it on your own computer, not in Docker, from the backend folder:
    python -m scripts.face_match_check --enrol ../face_test/passport.jpg ../face_test/*.jpg

The two face models (OpenCV Zoo: YuNet finds faces, SFace makes the face
code) are downloaded into backend/models/ on the first run.

Privacy: photos are only read. Nothing is saved, uploaded or logged, and
only file names and numbers are printed. Keep the photos in a git-ignored
folder (face_test/) and delete them after the test.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from app.services import face_models

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
# Larger photos are made smaller first, so detection stays fast.
MAX_SIDE = 1280
# How sure YuNet must be before something counts as a face (0–1).
DETECTION_SCORE = 0.8
# SFace's published cosine limit: at or above it, the same person.
SAME_PERSON_COSINE = 0.363


def read_image(path: Path) -> np.ndarray | None:
    """The photo as an image, or None if it cannot be read.
    np.fromfile also works with non-English folder names on Windows."""
    if not path.is_file():
        return None
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if image is None:
        return None
    scale = MAX_SIDE / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return image


def find_faces(detector, image: np.ndarray) -> np.ndarray:
    """One row per face: box (x, y, w, h), 5 landmarks, detection score."""
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    return faces if faces is not None else np.empty((0, 15))


def face_quality(image: np.ndarray, face: np.ndarray) -> dict:
    """Numbers the guided capture will check: size, sharpness, light, pose."""
    x, y, w, h = (int(v) for v in face[:4])
    crop = image[max(y, 0) : y + h, max(x, 0) : x + w]
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    right_eye, left_eye, nose = face[4:6], face[6:8], face[8:10]
    eye_gap = max(float(np.linalg.norm(left_eye - right_eye)), 1.0)
    eyes_middle_x = (right_eye[0] + left_eye[0]) / 2
    return {
        "face_px": w,
        "face_share": w / image.shape[1],
        "sharpness": cv2.Laplacian(grey, cv2.CV_64F).var(),
        "brightness": float(grey.mean()),
        # 0 = looking straight; about ±0.3 or more = clearly turned.
        "turn": float((nose[0] - eyes_middle_x) / eye_gap),
    }


def face_code(recogniser, image: np.ndarray, face: np.ndarray) -> np.ndarray:
    """The SFace face code (128 numbers) of one face."""
    aligned = recogniser.alignCrop(image, face)
    return recogniser.feature(aligned)


def check(recogniser, detector, path: Path) -> tuple[dict, np.ndarray | None]:
    """Quality numbers and the face code of the largest face in the photo."""
    image = read_image(path)
    if image is None:
        return {"problem": "cannot read"}, None
    faces = find_faces(detector, image)
    if len(faces) == 0:
        return {"faces": 0, "problem": "no face"}, None
    largest = max(faces, key=lambda face: face[2] * face[3])
    info = {"faces": len(faces), **face_quality(image, largest)}
    return info, face_code(recogniser, image, largest)


def print_row(name: str, info: dict, score: float | None) -> None:
    if "face_px" not in info:
        print(f"{name:<28} {info.get('faces', '-'):>5}  {info['problem']}")
        return
    match = "-" if score is None else f"{score:6.3f}"
    same = "" if score is None else ("same" if score >= SAME_PERSON_COSINE else "different")
    print(
        f"{name:<28} {info['faces']:>5} {info['face_px']:>6} {info['face_share']:>6.0%}"
        f" {info['sharpness']:>8.0f} {info['brightness']:>6.0f} {info['turn']:>6.2f}"
        f"  {match:>6}  {same}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--enrol", type=Path, required=True, help="the passport-size photo")
    parser.add_argument("photos", type=Path, nargs="+", help="test photos to compare with it")
    args = parser.parse_args()

    try:
        paths = face_models.ensure_models(MODELS_DIR)
    except (OSError, face_models.ModelDownloadError) as exc:
        sys.exit(f"The face models could not be downloaded: {exc}")
    detector = cv2.FaceDetectorYN.create(
        str(paths[face_models.DETECTOR]), "", (320, 320), DETECTION_SCORE
    )
    recogniser = cv2.FaceRecognizerSF.create(str(paths[face_models.RECOGNISER]), "")

    print(
        f"{'Photo':<28} {'Faces':>5} {'FacePx':>6} {'Width':>6}"
        f" {'Sharp':>8} {'Light':>6} {'Turn':>6}  {'Match':>6}"
    )
    enrol_info, enrol_code = check(recogniser, detector, args.enrol)
    print_row(f"{args.enrol.name} (enrol)", enrol_info, None)
    if enrol_code is None:
        sys.exit("The enrolment photo has no usable face. Use another photo.")

    for path in args.photos:
        if path.resolve() == args.enrol.resolve():
            continue
        info, code = check(recogniser, detector, path)
        score = None
        if code is not None:
            score = float(recogniser.match(enrol_code, code, cv2.FaceRecognizerSF_FR_COSINE))
        print_row(path.name, info, score)

    print(
        "\nMatch: SFace cosine similarity, higher = more alike;"
        f" {SAME_PERSON_COSINE} is SFace's published same-person limit."
        "\nWidth: face width as a share of the photo. Light: 0 dark – 255 bright."
        "\nTurn: 0 = looking straight, about ±0.3 or more = clearly turned."
    )


if __name__ == "__main__":
    main()
