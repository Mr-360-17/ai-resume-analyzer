"""Module 3: find skills from a controlled dictionary, plus education/experience hints."""
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

DEGREE_PATTERNS = {
    "Ph.D.": r"\bph\.?d\b|\bdoctorate\b",
    # Single-letter forms need the dot ("b.e"), otherwise words like "be" or "me" match.
    "Master's": r"\bm\.?tech\b|\bm\.e\b|\bm\.?sc\b|\bmca\b|\bmba\b|\bmaster'?s? (?:of|in|degree)\b",
    "Bachelor's": r"\bb\.?tech\b|\bb\.e\b|\bb\.?sc\b|\bbca\b|\bb\.?com\b|\bbachelor'?s?\b",
    "Diploma": r"\bdiploma\b",
}
DURATION_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(years?|yrs?|months?)\b")


@lru_cache(maxsize=1)
def load_skill_dictionary() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "skill_dictionary.csv")
    df["aliases"] = df["aliases"].str.split("|")
    return df


def alias_pattern(alias: str) -> re.Pattern:
    """Regex that matches an alias as a whole term.

    Plain \\b fails for skills ending in symbols (c++, c#), so the boundary is
    "not preceded or followed by a letter, digit, + or #".
    """
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![a-z0-9+#]){escaped}(?![a-z0-9+#])")


@lru_cache(maxsize=1)
def compiled_aliases() -> list[tuple[str, str, list[re.Pattern]]]:
    df = load_skill_dictionary()
    return [
        (row.skill, row.category, [alias_pattern(a) for a in row.aliases])
        for row in df.itertuples()
    ]


def extract_skills(clean_text: str) -> dict[str, dict]:
    """Return {skill: {"category": ..., "count": ..., "matched": alias}} for skills found."""
    found = {}
    for skill, category, patterns in compiled_aliases():
        count, matched = 0, None
        for pattern in patterns:
            hits = pattern.findall(clean_text)
            if hits:
                count += len(hits)
                matched = matched or hits[0]
        if count:
            found[skill] = {"category": category, "count": count, "matched": matched}
    return found


def group_by_category(skills: dict[str, dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for skill, info in skills.items():
        grouped.setdefault(info["category"], []).append(skill)
    return grouped


def extract_education(text: str) -> list[str]:
    return [name for name, pattern in DEGREE_PATTERNS.items() if re.search(pattern, text)]


def extract_experience_years(text: str) -> float | None:
    """Total of the 'N years' / 'N months' durations in the experience text, in years."""
    total = 0.0
    for value, unit in DURATION_RE.findall(text):
        total += float(value) / 12 if unit.startswith("month") else float(value)
    return round(total, 1) if total else None


EVIDENCE_SECTIONS = ("projects", "experience")


def skill_evidence(skills: dict[str, dict], sections: dict[str, str]) -> dict[str, list[str]]:
    """Which sections mention each skill.

    A skill used in projects or experience is "demonstrated"; one that only
    appears in a skills list is "listed only" and reported as a weak skill.
    """
    patterns = {s: p for s, _, p in compiled_aliases()}
    evidence = {}
    for skill in skills:
        evidence[skill] = [
            name for name, text in sections.items()
            if any(p.search(text) for p in patterns[skill])
        ]
    return evidence


def weak_skills(skills: dict[str, dict], sections: dict[str, str]) -> list[str]:
    """Skills never shown in projects/experience. Empty if those sections were not detected."""
    if not any(s in sections for s in EVIDENCE_SECTIONS):
        return []
    evidence = skill_evidence(skills, sections)
    return [s for s, where in evidence.items() if not set(where) & set(EVIDENCE_SECTIONS)]
