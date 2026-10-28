"""Check an application form link: print the form's title and public link.

Nothing is changed. Usage (inside the backend container), with the form's
editing address in quotes:
    python -m scripts.form_check "https://docs.google.com/forms/d/.../edit"
"""

import sys

from app.core.errors import AppError
from app.services.google_forms import get_form

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Give the form's editing address in quotes.")
    try:
        form = get_form(sys.argv[1])
    except AppError as error:
        sys.exit(error.message)
    print(f"Form: {form.title}")
    print(f"Public link: {form.public_url}")
    print(f"Accepting responses: {'yes' if form.accepts_responses else 'no'}")
    print(f"Has a file upload question: {'yes' if form.has_file_upload else 'no'}")
    print(f"Has a required photo upload: {'yes' if form.has_photo_upload else 'no'}")
    print(f"Has a required consent question: {'yes' if form.has_consent_question else 'no'}")
