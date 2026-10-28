"""Downloads files from Google Drive, read-only.

Used for the CVs candidates upload through the application form.
"""

import io

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from app.core.errors import NotFoundError
from app.services.google_client import (
    SIGN_IN_EXPIRED,
    GoogleUnavailableError,
    google_service,
)
from app.services.text_extraction import FileTooLargeError


def download_file(file_id: str, max_mb: int) -> bytes:
    """Return a file's content. The size is checked before downloading."""
    try:
        files = google_service("drive", "v3").files()
        size = int(files.get(fileId=file_id, fields="size").execute().get("size", 0))
        if size > max_mb * 1024 * 1024:
            raise FileTooLargeError(f"The file is larger than {max_mb} MB.")

        buffer = io.BytesIO()
        download = MediaIoBaseDownload(buffer, files.get_media(fileId=file_id))
        done = False
        while not done:
            _, done = download.next_chunk()
        return buffer.getvalue()
    except GoogleAuthError as exc:
        raise GoogleUnavailableError(SIGN_IN_EXPIRED) from exc
    except HttpError as exc:
        if exc.status_code in (403, 404):
            raise NotFoundError("The file could not be found in Google Drive.") from exc
        raise GoogleUnavailableError("Google Drive could not be reached.") from exc
