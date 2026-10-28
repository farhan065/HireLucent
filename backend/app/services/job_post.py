"""Builds the public job post from an approved job description."""

from html import escape

from markdown_it import MarkdownIt

# Raw HTML in a description is shown as text, never passed into the page.
_markdown = MarkdownIt("commonmark", {"html": False})


def post_html(description: str, job_code: str, form_url: str) -> str:
    """The post body: the description, then how to apply.

    The description is not rewritten, so the post says what was approved.
    """
    body = _markdown.render(description)
    # A blog theme shows the post title as the page heading, so the
    # description's sections become smaller headings under it.
    body = body.replace("<h2>", "<h3>").replace("</h2>", "</h3>")
    return (
        f"{body}"
        "<h3>How to apply</h3>\n"
        "<p>Submit your CV through the application form. "
        f"Job code: <strong>{escape(job_code)}</strong></p>\n"
        f'<p><a href="{escape(form_url, quote=True)}">Apply now</a></p>\n'
    )
