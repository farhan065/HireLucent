"""The two face models from the OpenCV Zoo, and how they are downloaded.

YuNet (MIT licence) finds faces and their landmarks; SFace (Apache 2.0)
turns a face into a face code. Both run locally on the CPU, so no photo
ever leaves the computer.

The backend image downloads them when it is built:
    python -m app.services.face_models /app/models

Each file is checked against its SHA-256, so a damaged or changed
download is refused. This module needs no settings, so it also runs
during the image build.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
DETECTOR = "face_detection_yunet_2023mar.onnx"
RECOGNISER = "face_recognition_sface_2021dec.onnx"
URLS = {
    DETECTOR: f"{BASE_URL}/face_detection_yunet/{DETECTOR}",
    RECOGNISER: f"{BASE_URL}/face_recognition_sface/{RECOGNISER}",
}
SHA256 = {
    DETECTOR: "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    RECOGNISER: "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
}


class ModelDownloadError(RuntimeError):
    """A model file could not be downloaded, or it was not the right file."""


def is_valid(path: Path, name: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256[name]


def ensure_models(folder: Path) -> dict[str, Path]:
    """Both model files in the folder, downloading any that are missing.
    Returns their paths by file name."""
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, url in URLS.items():
        path = folder / name
        if not is_valid(path, name):
            print(f"Downloading {name} ...")
            urllib.request.urlretrieve(url, path)
            if not is_valid(path, name):
                path.unlink(missing_ok=True)
                raise ModelDownloadError(f"{name} did not download correctly.")
        paths[name] = path
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("models")
    try:
        ensure_models(target)
    except (OSError, ModelDownloadError) as exc:
        sys.exit(f"The face models could not be downloaded: {exc}")
    print(f"Face models ready in {target}")
