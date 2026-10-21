"""The fairness check in code: rules every feedback email must pass before
the interviewer sees it as ready, and again after the interviewer edits it.

The rules are plain code, so they are the same every time and easy to
explain. They only guard safety (scores, other candidates, personal topics,
personal data, promises, offer details, quotes, placeholders, and named
skills or tools the candidate's results do not contain); the wording itself
is free. Each warning names what it found, so the screen can say exactly
what is wrong and highlight those words. The AI review
(writing.review_email) comes after these rules and judges meaning.
"""

import re

from app.graphs.feedback import templates
from app.services.interview_emails import HTML_TAG

MIN_QUOTE_WORDS = 4
MIN_PHONE_DIGITS = 9

# (code, what the interviewer is told, pattern)
RULES: list[tuple[str, str, re.Pattern]] = [
    (
        "score",
        "Mentions a score, rank or percentage. These are never shared with candidates",
        re.compile(
            r"\b\d{1,3}(?:\.\d+)?\s?%|\bscor(?:e|ed|es|ing)\b|\branked\b|\branking\b"
            r"|\brank\b|\bout of (?:10|100)\b|\bpercent(?:age)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "other_candidates",
        "Mentions other candidates. Each email is about this candidate only",
        re.compile(
            r"\bother (?:candidates?|applicants?)\b|\banother (?:candidate|applicant)\b"
            r"|\bsomeone else\b|\b(?:stronger|better|more suitable) (?:candidates?|applicants?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "personal",
        "Mentions a personal topic. Feedback is about job-related skills only",
        re.compile(
            r"\b(?:age|aged|years old|young|younger|elderly|gender|male|female|pregnan\w*"
            r"|married|marital|religio\w*|muslim|hindu|christian|buddhist|nationality"
            r"|ethnic\w*|race|racial|caste|disab\w*|health|illness|accent|appearance"
            r"|children|family)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "promise",
        "Promises something the company may not keep",
        re.compile(
            r"\bguarantee\w*|\bwe will (?:definitely |surely )?(?:consider|contact|hire|keep)"
            r" you\b|\bnext (?:opening|vacancy|position|role)\b|\bfuture (?:openings?|vacanc\w+)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "offer",
        "Mentions offer details. Salary, start date and contract terms belong to the offer",
        re.compile(
            r"\bsalar\w*|\bcompensation\b|\bstart(?:ing)? date\b|\bjoining date\b|\bcontract\b"
            r"|\boffer letter\b|\byou are hired\b|\bbenefits package\b",
            re.IGNORECASE,
        ),
    ),
    (
        "identity",
        "Mentions the identity check, which is only for the interviewer",
        re.compile(r"\bidentity\b|\bface (?:match|check)\b|\bverification photo\b", re.IGNORECASE),
    ),
]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LINK = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
QUOTE = re.compile(r"[\"“”]([^\"“”]{3,})[\"“”]")
PLACEHOLDER = re.compile(r"\[[^\]]{1,40}\]")

# Named skills and tools: words with a dot or a digit (Next.js, ES6),
# capitals inside or all capitals (TypeScript, AWS), and capitalised words
# in the middle of a sentence (Kubernetes).
WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#]*(?:[.-][A-Za-z0-9+#]+)*")
SENTENCE_START = (".", "!", "?", ":", "\n", "-", "•", "*", "(")
COMMON_CAPITALISED = {
    "i", "we", "our", "you", "your", "dear", "hirelucent", "careers", "cv", "pdf", "word",
    "thank", "thanks", "with", "best", "kind", "warm", "regards", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october", "november",
    "december", "english",
}


def _warning(code: str, message: str, words: list[str], text: str, at: int) -> dict:
    shown = ", ".join(f'"{word}"' for word in dict.fromkeys(words))
    return {
        "code": code,
        "message": f"{message}: {shown}" if shown else message,
        "quote": _sentence(text, at).strip()[:160],
        "words": list(dict.fromkeys(words))[:8],
    }


def _sentence(text: str, at: int) -> str:
    """The sentence around a position, for showing where a word is."""
    left = max(text.rfind(".", 0, at), text.rfind("\n", 0, at)) + 1
    stops = [index for index in (text.find(".", at), text.find("\n", at)) if index != -1]
    right = min(stops) + 1 if stops else len(text)
    return text[left:right]


def _is_phone(text: str) -> bool:
    return len(re.sub(r"\D", "", text)) >= MIN_PHONE_DIGITS


def rule_warnings(body: str, first_name: str = "", known: str = "") -> list[dict]:
    """Every safety rule the email breaks, one warning per rule with the words
    found. Words that are part of the job's own requirements (known) are
    not personal topics, for example "health" in a healthcare role."""
    text = body.replace(first_name, templates.NAME) if first_name else body
    known_lower = known.lower()
    found: list[dict] = []
    for code, message, pattern in RULES:
        matches = [m for m in pattern.finditer(text) if m.group(0).lower() not in known_lower]
        if matches:
            words = [m.group(0) for m in matches]
            found.append(_warning(code, message, words, text, matches[0].start()))
    personal = [m for m in EMAIL.finditer(text)] + [m for m in LINK.finditer(text)]
    personal += [m for m in PHONE.finditer(text) if _is_phone(m.group(0))]
    if personal:
        personal.sort(key=lambda m: m.start())
        found.append(
            _warning(
                "personal_data",
                "Has contact details or a link. Emails never carry personal data",
                [m.group(0) for m in personal],
                text,
                personal[0].start(),
            )
        )
    for match in QUOTE.finditer(text):
        if len(match.group(1).split()) >= MIN_QUOTE_WORDS:
            found.append(
                _warning(
                    "quote",
                    "Quotes the interview or the CV word for word. Describe it instead",
                    [match.group(0)],
                    text,
                    match.start(),
                )
            )
            break
    leftovers = [m for m in PLACEHOLDER.finditer(text) if m.group(0) != templates.NAME]
    html = HTML_TAG.search(text)
    if leftovers or html:
        first = html or leftovers[0]
        found.append(
            _warning(
                "format",
                "Has HTML or a placeholder in square brackets",
                [m.group(0) for m in leftovers] + ([html.group(0)] if html else []),
                text,
                first.start(),
            )
        )
    return found


def _at_sentence_start(text: str, at: int) -> bool:
    before = text[:at].rstrip(" \t")
    return not before or before.endswith(SENTENCE_START) or before.endswith("Dear")


def _is_named_term(word: str, text: str, at: int) -> bool:
    if any(ch.isdigit() for ch in word) or "." in word.strip("."):
        return True
    if len(word) > 1 and (word.isupper() or any(ch.isupper() for ch in word[1:])):
        return True
    return word[0].isupper() and not _at_sentence_start(text, at)


def _known(word: str, known_lower: str) -> bool:
    word = word.lower().strip(".-")
    variants = {word, word.removesuffix("s"), word.removesuffix("'s"), word.removesuffix("es")}
    return any(variant and variant in known_lower for variant in variants)


def unknown_terms(body: str, first_name: str, known: str) -> list[str]:
    """Named skills or tools in the email that the candidate's points, the
    job title and the job's requirements never mention, for example
    "Kubernetes" when nothing about it was ever judged."""
    text = body.replace(first_name, templates.NAME) if first_name else body
    text = text.replace(templates.NAME, "").replace(templates.SIGNATURE, "")
    known_lower = known.lower()
    found = []
    for match in WORD.finditer(text):
        word = match.group(0).strip(".-")
        if len(word) < 2 or word.lower() in COMMON_CAPITALISED:
            continue
        if _is_named_term(word, text, match.start()) and not _known(word, known_lower):
            found.append(word)
    return list(dict.fromkeys(found))


def invented_warning(words: list[str], body: str) -> dict:
    at = max(body.find(words[0]), 0) if words else 0
    return _warning(
        "invented", "Mentions something not in the candidate's results", words, body, at
    )


def codes(warnings: list[dict]) -> list[str]:
    return sorted({warning["code"] for warning in warnings})


def problem_text(warnings: list[dict]) -> list[str]:
    """The warnings as instructions for a rewrite."""
    return [warning["message"] for warning in warnings]
