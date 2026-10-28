"""The fixed parts of every feedback email: subjects, the signature, the
role-level sentence, and the two messages that are never written by AI
(Hire, and a CV that could not be read).

The AI writes "[first name]" where the greeting goes; the real first name is
put in only here, so the AI provider never receives the candidate's name.
"""

from app.models.enums import FeedbackKind

NAME = "[first name]"
SIGNATURE = "With warm regards,\nHireLucent Careers"

SUBJECTS = {
    FeedbackKind.SCREENING_REJECT: "Thank you for applying – {job} at HireLucent",
    FeedbackKind.INTERVIEW_REJECT: "Thank you for interviewing – {job} at HireLucent",
    FeedbackKind.HIRE: "Congratulations – {job} at HireLucent",
    FeedbackKind.CV_UNREADABLE: "About your application – {job} at HireLucent",
}

# Why the skills matter, worded for the role's level.
SENIOR = "senior"
JUNIOR = "junior"
ENTRY = "entry"
LEVEL_SENTENCES = {
    SENIOR: "For this role, we need someone who can deliver in these areas from the very first day.",
    JUNIOR: (
        "For this role, we are looking for candidates who already have a little more "
        "grounding in these areas."
    ),
    ENTRY: (
        "For this opportunity, we are looking for candidates who have started building "
        "experience in these areas."
    ),
}
LEVEL_LABELS = {
    SENIOR: "experienced role",
    JUNIOR: "junior role",
    ENTRY: "internship or trainee role",
}
ENTRY_WORDS = ("intern", "trainee", "apprentice", "graduate")

HIRE_BODY = """Dear {name},

Thank you for joining the interview with us.

We are delighted to share some wonderful news: you have been selected for the {job} role!

Our team will be in touch with you soon about the next steps.

Congratulations, and thank you for the time and enthusiasm you brought to every stage of the process.

""" + SIGNATURE

CV_UNREADABLE_BODY = """Dear {name},

Thank you for your interest in the {job} role. We truly appreciate you thinking of us.

Unfortunately, we were not able to open the CV file you submitted, so we could not review your application. This sometimes happens when a file is damaged, password-protected or a low-quality scan.

We would genuinely love to learn more about you. If the role is still open, please feel free to apply again with your CV as a PDF or Word document.

""" + SIGNATURE

TEMPLATES = {FeedbackKind.HIRE: HIRE_BODY, FeedbackKind.CV_UNREADABLE: CV_UNREADABLE_BODY}
AI_KINDS = (FeedbackKind.SCREENING_REJECT, FeedbackKind.INTERVIEW_REJECT)


def role_level(job_title: str, min_years: int | None) -> str:
    """senior from 3 years of required experience, entry for internships and
    trainee roles, junior otherwise."""
    title = job_title.lower()
    if any(word in title for word in ENTRY_WORDS):
        return ENTRY
    if (min_years or 0) >= 3:
        return SENIOR
    return JUNIOR


# Titles and short forms written before a name, common in Bangladesh, that
# are not what the person is called: "Md. Tashsin Ahmed" is Tashsin.
NAME_PREFIXES = {"md", "mohd", "mst", "mr", "mrs", "ms", "miss", "dr", "engr", "prof", "sk"}


def first_name(full_name: str) -> str:
    """The name to greet the candidate with: the first part that is not a
    title or a short form, in normal capitals ("TASHSIN" becomes "Tashsin")."""
    parts = (full_name or "").strip().split()
    while len(parts) > 1 and parts[0].lower().rstrip(".") in NAME_PREFIXES:
        parts = parts[1:]
    if not parts:
        return "there"
    name = parts[0].strip(".,")
    if name.isupper() or name.islower():
        name = "-".join(piece.capitalize() for piece in name.split("-"))
    return name or "there"


def subject(kind: str, job_title: str) -> str:
    return SUBJECTS[FeedbackKind(kind)].format(job=job_title)


def fixed_body(kind: str, name: str, job_title: str) -> str:
    return TEMPLATES[FeedbackKind(kind)].format(name=name, job=job_title)


def finish(email: str, name: str) -> str:
    """The AI's email with the first name put in and the signature added."""
    return f"{email.strip().replace(NAME, name)}\n\n{SIGNATURE}"
