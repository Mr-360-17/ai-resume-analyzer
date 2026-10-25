"""Module 6b: rule-based learning roadmap for the missing skills of a target role.

Rules
1. Missing required skills come first, in the order the role lists them
   (roles list their core skills first), then missing nice-to-have skills.
2. Up to 6 skills: one skill per week. More than that: two per week, so the
   plan stays within about two months.
3. The last week is a portfolio project that uses the new skills, because a
   project on the resume is the evidence recruiters look for.
"""
from skill_extractor import load_skill_dictionary

ONE_PER_WEEK_LIMIT = 6
MAX_SKILLS = 12


def learning_topic(skill: str) -> str:
    df = load_skill_dictionary().set_index("skill")
    return df.loc[skill, "learning_topic"] if skill in df.index else f"Learn {skill}"


def generate_roadmap(role: str, missing_required: list[str], missing_nice: list[str]) -> list[dict]:
    skills = (missing_required + missing_nice)[:MAX_SKILLS]
    if not skills:
        return [{
            "week": 1,
            "skills": [],
            "focus": f"You already cover the listed skills for {role}. Build a larger "
                     "project or contribute to open source to show them in depth.",
        }]
    per_week = 1 if len(skills) <= ONE_PER_WEEK_LIMIT else 2
    plan = []
    for i in range(0, len(skills), per_week):
        chunk = skills[i:i + per_week]
        plan.append({
            "week": len(plan) + 1,
            "skills": chunk,
            "focus": "; ".join(learning_topic(s) for s in chunk),
        })
    capstone = ", ".join(skills[:3])
    plan.append({
        "week": len(plan) + 1,
        "skills": [],
        "focus": f"Portfolio project for {role}: build and publish a small project on "
                 f"GitHub that uses {capstone}, then add it to your resume.",
    })
    return plan
