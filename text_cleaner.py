"""Module 2b: clean resume text, remove personal information, detect sections."""
import re

# Lines mentioning these are dropped before any scoring (Responsible AI rules).
PROTECTED_PATTERNS = [
    r"\bgender\b", r"\bsex\s*:", r"\bdate of birth\b", r"\bdob\b", r"\bage\s*:",
    r"\bmarital status\b", r"\bmarried\b", r"\bunmarried\b", r"\breligion\b",
    r"\bnationality\b", r"\bcaste\b", r"\bdisability\b", r"\bphotograph\b",
    r"\bfather'?s name\b", r"\bmother'?s name\b",
]
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\s-]?){10,13}")
URL_RE = re.compile(r"(?:https?://|www\.)\S+")

SECTION_HEADINGS = {
    "education": ["education", "academic background", "academics", "qualifications"],
    "skills": ["skills", "technical skills", "key skills", "core competencies", "tech stack"],
    "projects": ["projects", "academic projects", "personal projects", "key projects"],
    "experience": ["experience", "work experience", "professional experience",
                   "internships", "internship", "employment history"],
    "certifications": ["certifications", "certificates", "courses"],
}


def remove_personal_info(text: str) -> tuple[str, int]:
    """Drop lines with protected attributes or contact details; mask URLs.

    Returns the filtered text and the number of lines removed.
    """
    kept, removed = [], 0
    for line in text.splitlines():
        lower = line.lower()
        if (any(re.search(p, lower) for p in PROTECTED_PATTERNS)
                or EMAIL_RE.search(line) or PHONE_RE.search(line)):
            removed += 1
            continue
        kept.append(URL_RE.sub(" ", line))
    return "\n".join(kept), removed


def clean_text(text: str) -> str:
    """Lowercase and normalise text while keeping C++, C#, .NET, node.js, CI/CD."""
    text = text.lower()
    text = text.replace("–", "-").replace("—", "-").replace("•", " ")
    # Keep letters, digits, and the symbols that are part of skill names.
    text = re.sub(r"[^a-z0-9+#./\-\n ]", " ", text)
    # A full stop or slash at the end of a word is punctuation, not part of a skill.
    text = re.sub(r"(?<=[a-z0-9])[./](?=\s|$)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def detect_sections(raw_text: str) -> dict[str, str]:
    """Split the resume into sections using common heading names.

    A line counts as a heading when it is short and matches a known name.
    Text before the first heading is stored under "header".
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in raw_text.splitlines():
        stripped = re.sub(r"[^a-z ]", "", line.lower()).strip()
        matched = None
        if 0 < len(stripped) <= 30:
            for name, headings in SECTION_HEADINGS.items():
                if stripped in headings:
                    matched = name
                    break
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def prepare(raw_text: str) -> dict:
    """Run the full cleaning pipeline and return everything later stages need."""
    filtered, removed = remove_personal_info(raw_text)
    sections = detect_sections(filtered)
    return {
        "clean_text": clean_text(filtered),
        "sections": {k: clean_text(v) for k, v in sections.items()},
        "removed_personal_lines": removed,
    }
