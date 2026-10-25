"""Runs the full analysis for one resume. Used by app.py and the tests."""
from job_matcher import custom_role_from_description, rank_roles
from resume_parser import extract_text
from roadmap_generator import generate_roadmap
from skill_extractor import (
    extract_education, extract_experience_years, extract_skills,
    group_by_category, skill_evidence, weak_skills,
)
from text_cleaner import prepare


def analyze_text(raw_text: str, job_description: str = "") -> dict:
    prepared = prepare(raw_text)
    text, sections = prepared["clean_text"], prepared["sections"]
    skills = extract_skills(text)
    extra_roles = [custom_role_from_description(job_description)] if job_description.strip() else []
    ranking = rank_roles(text, set(skills), extra_roles)
    return {
        "clean_text": text,
        "sections": sections,
        "removed_personal_lines": prepared["removed_personal_lines"],
        "skills": skills,
        "skills_by_category": group_by_category(skills),
        "evidence": skill_evidence(skills, sections),
        "weak_skills": weak_skills(skills, sections),
        "education": extract_education(text),
        "experience_years": extract_experience_years(sections.get("experience", "")),
        "ranking": ranking,
    }


def analyze_file(filename: str, data: bytes, job_description: str = "") -> dict:
    return analyze_text(extract_text(filename, data), job_description)


def role_result(analysis: dict, role: str) -> dict:
    """Score row, weak skills and roadmap for one target role."""
    row = analysis["ranking"].set_index("role").loc[role].to_dict()
    row["role"] = role
    row["weak"] = [s for s in row["found_required"] if s in analysis["weak_skills"]]
    row["roadmap"] = generate_roadmap(role, row["missing_required"], row["missing_nice"])
    return row
