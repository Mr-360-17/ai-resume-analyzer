"""Evaluation script for the brief's testing checklist.

Writes tests/test_cases.csv (expected vs actual top role for each sample resume)
and runs checks for extraction, skill precision/recall, score consistency,
fairness and edge cases. Run from the project root:

    python tests/run_tests.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from job_matcher import rank_roles  # noqa: E402
from pipeline import analyze_file, analyze_text, role_result  # noqa: E402
from resume_parser import ResumeError, extract_text  # noqa: E402
from skill_extractor import extract_skills  # noqa: E402
from text_cleaner import clean_text  # noqa: E402

SAMPLES = ROOT / "data" / "sample_resumes"

# Expected top role and the skills a human reader would list for each sample.
CASES = [
    ("resume_A_data_analyst.pdf", "Data Analyst",
     {"Python", "Pandas", "NumPy", "SQL", "MySQL", "Excel", "Power BI", "Tableau",
      "Statistics", "Data Visualization", "EDA", "Data Cleaning"}),
    ("resume_B_ml_engineer.docx", "Machine Learning Engineer",
     {"Python", "scikit-learn", "XGBoost", "Pandas", "NumPy", "SQL", "FastAPI", "Docker",
      "MLflow", "Git", "GitHub", "AWS", "Cloud Deployment", "Machine Learning", "REST APIs", "Regression",
      "Feature Engineering", "Model Evaluation", "Classification", "CI/CD"}),
    ("resume_C_nlp_engineer.pdf", "NLP Engineer",
     {"Python", "NLP", "spaCy", "NLTK", "Hugging Face", "Transformers", "PyTorch",
      "TF-IDF", "Word Embeddings", "scikit-learn", "Text Classification",
      "Named Entity Recognition", "Regression"}),
    ("resume_D_cv_engineer.docx", "Computer Vision Engineer",
     {"Python", "OpenCV", "PyTorch", "TensorFlow", "CNN", "YOLO", "Deep Learning", "NumPy",
      "Object Detection", "Image Segmentation", "Computer Vision"}),
    ("resume_E_web_developer.pdf", "Web Developer",
     {"HTML", "CSS", "JavaScript", "React", "TypeScript", "Git", "GitHub", "REST APIs",
      "Node.js"}),
]

failures = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not condition:
        failures.append(name)


def role_ranking_and_skills() -> None:
    rows, tp, fp, fn = [], 0, 0, 0
    for filename, expected_role, true_skills in CASES:
        analysis = analyze_file(filename, (SAMPLES / filename).read_bytes())
        top = analysis["ranking"].iloc[0]
        found = set(analysis["skills"])
        tp += len(found & true_skills)
        fp += len(found - true_skills)
        fn += len(true_skills - found)
        ok = top["role"] == expected_role
        rows.append({
            "test_resume": filename,
            "expected_top_role": expected_role,
            "actual_top_role": top["role"],
            "match_score": top["match_score"],
            "second_role": analysis["ranking"].iloc[1]["role"],
            "skills_found": len(found),
            "result": "Pass" if ok else "Fail",
            "comments": (f"Extra: {', '.join(sorted(found - true_skills)) or '-'}; "
                         f"missed: {', '.join(sorted(true_skills - found)) or '-'}"),
        })
        check(f"top role for {filename}", ok, f"{top['role']} {top['match_score']}%")
    pd.DataFrame(rows).to_csv(ROOT / "tests" / "test_cases.csv", index=False)
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    check("skill precision >= 0.9", precision >= 0.9, f"{precision:.2f}")
    check("skill recall >= 0.9", recall >= 0.9, f"{recall:.2f}")


def extraction_quality() -> None:
    for filename, *_ in CASES:
        text = extract_text(filename, (SAMPLES / filename).read_bytes())
        check(f"text extracted from {filename}", len(text) > 300, f"{len(text)} chars")


def symbol_skills() -> None:
    found = extract_skills(clean_text("Worked with C++, C#, .NET, Node.js and CI/CD."))
    check("keeps C++, C#, .NET, Node.js, CI/CD",
          {"C++", "C#", ".NET", "Node.js", "CI/CD"} <= set(found), ", ".join(found))
    found = extract_skills(clean_text("I like html and mysql; my name is Ann; we went to the gym."))
    check("no false matches inside words (ml in html, sql in mysql handled)",
          "Machine Learning" not in found, ", ".join(found))


def score_consistency() -> None:
    base = "Skills: Python, SQL, Excel. Built dashboards."
    roles_before = rank_roles(clean_text(base), set(extract_skills(clean_text(base)))).set_index("role")
    richer = base + " Also Pandas, Power BI and statistics."
    roles_after = rank_roles(clean_text(richer), set(extract_skills(clean_text(richer)))).set_index("role")
    before, after = roles_before.loc["Data Analyst", "match_score"], roles_after.loc["Data Analyst", "match_score"]
    check("adding role skills raises the score", after > before, f"{before} -> {after}")

    a = analyze_text(base + " Docker.")
    b = analyze_text(base)
    da = a["ranking"].set_index("role").loc["Data Analyst", "skill_coverage"]
    db = b["ranking"].set_index("role").loc["Data Analyst", "skill_coverage"]
    check("unrelated skill does not change role skill coverage", da == db, f"{db} vs {da}")


def fairness() -> None:
    body = ("Skills\nPython, SQL, Pandas, Power BI, Excel, Statistics\n"
            "Projects\nSales dashboard in Power BI using SQL and Pandas.\n")
    plain = analyze_text(body)
    with_personal = analyze_text(
        "Gender: Female\nDate of Birth: 01/01/2000\nMarital Status: Single\n"
        "Religion: Any\nNationality: Any\nEmail: someone@example.com\n" + body
    )
    s1 = plain["ranking"].set_index("role")["match_score"]
    s2 = with_personal["ranking"].set_index("role")["match_score"]
    check("protected attributes do not change any score", s1.equals(s2))
    check("personal-detail lines are removed", with_personal["removed_personal_lines"] == 6,
          str(with_personal["removed_personal_lines"]))
    check("email is masked", "example.com" not in with_personal["clean_text"])


def edge_cases() -> None:
    for name, data, label in [
        ("resume.txt", b"hello", "rejects .txt"),
        ("resume.pdf", b"", "rejects empty file"),
        ("resume.pdf", b"not a pdf", "rejects corrupt PDF"),
        ("resume.pdf", b"x" * (6 * 1024 * 1024), "rejects file over 5 MB"),
    ]:
        try:
            extract_text(name, data)
            check(label, False)
        except ResumeError:
            check(label, True)


def target_role_output() -> None:
    analysis = analyze_file("resume_B_ml_engineer.docx",
                            (SAMPLES / "resume_B_ml_engineer.docx").read_bytes())
    target = role_result(analysis, "AI Engineer")
    check("roadmap covers every missing required skill",
          set(target["missing_required"]) <= {s for w in target["roadmap"] for s in w["skills"]})
    jd = "We need an engineer with Python, Kubernetes, Terraform-free AWS and Docker skills."
    with_jd = analyze_file("resume_B_ml_engineer.docx",
                           (SAMPLES / "resume_B_ml_engineer.docx").read_bytes(), jd)
    check("custom job description becomes a role",
          "Custom job description" in set(with_jd["ranking"]["role"]))


if __name__ == "__main__":
    extraction_quality()
    role_ranking_and_skills()
    symbol_skills()
    score_consistency()
    fairness()
    edge_cases()
    target_role_output()
    print(f"\n{len(failures)} failure(s)" if failures else "\nAll checks passed")
    sys.exit(1 if failures else 0)
