"""Modules 4-6: load job roles, score the resume against each role, find skill gaps.

Match score (0-100) = 70% skill coverage + 30% TF-IDF text similarity.

* Skill coverage: share of the role's skills found in the resume. Required
  skills count fully, nice-to-have skills count half.
* Text similarity: cosine similarity between TF-IDF vectors of the resume and
  the role profile (description + skill names + aliases). It rewards related
  wording that the skill dictionary does not list.
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skill_extractor import extract_skills, load_skill_dictionary
from text_cleaner import clean_text

DATA_DIR = Path(__file__).parent / "data"
SKILL_WEIGHT = 0.7
TEXT_WEIGHT = 0.3
NICE_TO_HAVE_WEIGHT = 0.5
# Keeps c++, c#, node.js and ci/cd as single tokens.
TOKEN_PATTERN = r"(?u)[a-z0-9][a-z0-9+#./]*[a-z0-9+#]|[a-z0-9]"


@lru_cache(maxsize=1)
def load_job_roles() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "job_roles.csv")
    df["required_skills"] = df["required_skills"].str.split(";")
    df["nice_to_have"] = df["nice_to_have"].fillna("").str.split(";").apply(
        lambda xs: [x for x in xs if x]
    )
    return df


def role_profile(description: str, skills: list[str]) -> str:
    """Text used for the TF-IDF side of a role: description, skills and their aliases."""
    dictionary = load_skill_dictionary().set_index("skill")
    alias_words = []
    for skill in skills:
        if skill in dictionary.index:
            alias_words.extend(dictionary.loc[skill, "aliases"])
    return clean_text(" ".join([description, *skills, *alias_words]))


def custom_role_from_description(job_description: str, title: str = "Custom job description") -> dict:
    """Turn a pasted job description into a role: every skill it mentions is required."""
    skills = list(extract_skills(clean_text(job_description)))
    return {"role": title, "required_skills": skills, "nice_to_have": [], "description": job_description}


def text_similarities(resume_text: str, profiles: list[str]) -> list[float]:
    vectorizer = TfidfVectorizer(
        token_pattern=TOKEN_PATTERN, stop_words="english",
        ngram_range=(1, 2), sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([resume_text, *profiles])
    return cosine_similarity(matrix[0], matrix[1:]).ravel().tolist()


def score_role(resume_skills: set[str], required: list[str], nice: list[str], text_sim: float) -> dict:
    found_req = [s for s in required if s in resume_skills]
    found_nice = [s for s in nice if s in resume_skills]
    total = len(required) + NICE_TO_HAVE_WEIGHT * len(nice)
    coverage = (len(found_req) + NICE_TO_HAVE_WEIGHT * len(found_nice)) / total if total else 0.0
    score = 100 * (SKILL_WEIGHT * coverage + TEXT_WEIGHT * text_sim)
    return {
        "match_score": round(score, 1),
        "skill_coverage": round(100 * coverage, 1),
        "text_similarity": round(100 * text_sim, 1),
        "found_required": found_req,
        "missing_required": [s for s in required if s not in resume_skills],
        "found_nice": found_nice,
        "missing_nice": [s for s in nice if s not in resume_skills],
    }


def rank_roles(resume_text: str, resume_skills: set[str], extra_roles: list[dict] | None = None) -> pd.DataFrame:
    """Score every role and return them sorted from best to worst match."""
    roles = load_job_roles().to_dict("records") + (extra_roles or [])
    profiles = [role_profile(r["description"], r["required_skills"] + r["nice_to_have"]) for r in roles]
    sims = text_similarities(resume_text, profiles)
    rows = []
    for role, sim in zip(roles, sims):
        result = score_role(resume_skills, role["required_skills"], role["nice_to_have"], sim)
        rows.append({"role": role["role"], **result})
    return pd.DataFrame(rows).sort_values("match_score", ascending=False).reset_index(drop=True)
