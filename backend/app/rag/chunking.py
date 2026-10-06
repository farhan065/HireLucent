"""Splits text into pieces small enough to embed and search well."""

MAX_CHUNK_CHARS = 1200
OVERLAP_CHARS = 150


def chunk_text(
    text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS
) -> list[str]:
    """Split a document into chunks made of whole paragraphs.

    Paragraphs are added to a chunk until it is full. The next chunk starts
    with the end of the previous one, so a sentence that falls on a boundary
    is still found by a search.
    """
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        # A single very long paragraph is cut into pieces of the allowed size.
        while len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars - overlap :]

        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = current[-overlap:] + "\n\n" + paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph

    if current:
        chunks.append(current)
    return chunks


def split_questions(text: str) -> list[str]:
    """One question per line. Numbering and bullet marks are removed."""
    questions = []
    for line in text.splitlines():
        cleaned = line.strip().lstrip("-*•0123456789.) ").strip()
        if len(cleaned) >= 10:
            questions.append(cleaned)
    return questions
