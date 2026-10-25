"""AI Resume Analyzer and Job Recommendation System - Streamlit dashboard.

Run:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from job_matcher import SKILL_WEIGHT, TEXT_WEIGHT, load_job_roles
from pipeline import analyze_file, role_result
from report_generator import DISCLAIMER, build_pdf
from resume_parser import MAX_FILE_SIZE_MB, ResumeError
from skill_extractor import load_skill_dictionary

SAMPLE_DIR = Path(__file__).parent / "data" / "sample_resumes"
REPORT_DIR = Path(__file__).parent / "reports"

st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄", layout="wide")


@st.cache_data(show_spinner=False, max_entries=20)
def run_analysis(filename: str, data: bytes, job_description: str) -> dict:
    return analyze_file(filename, data, job_description)


# ---------- Sidebar ----------
with st.sidebar:
    st.header("How it works")
    st.markdown(
        "1. Upload a PDF or DOCX resume\n"
        "2. Text is extracted, cleaned and personal details are removed\n"
        f"3. Skills are matched against a dictionary of {len(load_skill_dictionary())} skills\n"
        f"4. The resume is scored against {len(load_job_roles())} job roles\n"
        "5. Pick a target role to see missing skills and a roadmap"
    )
    st.markdown(
        f"**Match score** = {SKILL_WEIGHT:.0%} skill coverage + "
        f"{TEXT_WEIGHT:.0%} TF-IDF cosine similarity"
    )
    st.divider()
    st.subheader("Responsible AI")
    st.caption(DISCLAIMER)
    st.caption("Resumes are processed in memory and are not stored.")

# ---------- Input ----------
st.title("📄 AI Resume Analyzer & Job Recommender")
st.write("See how well your resume matches common tech roles, which skills are missing, "
         "and what to learn next.")

col_upload, col_sample = st.columns([3, 2])
with col_upload:
    uploaded = st.file_uploader(
        f"Upload your resume (PDF or DOCX, max {MAX_FILE_SIZE_MB} MB)", type=["pdf", "docx"]
    )
with col_sample:
    samples = sorted(p.name for p in SAMPLE_DIR.glob("*") if p.suffix in {".pdf", ".docx"})
    sample_choice = st.selectbox("...or try an anonymised sample resume", ["None"] + samples)

with st.expander("Optional: paste a job description to compare against"):
    job_description = st.text_area(
        "Job description", height=150, label_visibility="collapsed",
        placeholder="Paste a job posting here. Its skills become an extra 'Custom job description' role.",
    )

if uploaded is not None:
    filename, data = uploaded.name, uploaded.getvalue()
elif sample_choice != "None":
    filename, data = sample_choice, (SAMPLE_DIR / sample_choice).read_bytes()
else:
    st.info("Upload a resume or pick a sample to begin.")
    st.stop()

try:
    with st.spinner("Analysing resume..."):
        analysis = run_analysis(filename, data, job_description)
except ResumeError as err:
    st.error(str(err))
    st.stop()

ranking: pd.DataFrame = analysis["ranking"]
skills = analysis["skills"]
st.success(f"Analysed **{filename}**")

if not skills:
    st.warning("No skills from the dictionary were found. Check that the resume lists "
               "technical skills as text (not inside images).")

# ---------- Target role ----------
roles = ranking["role"].tolist()
target_role = st.selectbox("Target role", roles, index=0,
                           help="Defaults to your best-matching role.")
target = role_result(analysis, target_role)
best = ranking.iloc[0]
st.caption(f"Best-fit role: **{best['role']}** ({best['match_score']:.0f}%)")

m1, m2, m3 = st.columns(3)
m1.metric("Match score", f"{target['match_score']:.0f}%")
m2.metric("Skills found", len(skills))
m3.metric("Missing required skills", len(target["missing_required"]))

tab_overview, tab_skills, tab_gap, tab_roadmap, tab_report = st.tabs(
    ["Recommended roles", "Extracted skills", "Skill gap", "Learning roadmap", "Report"]
)

# ---------- Recommended roles ----------
with tab_overview:
    st.subheader("Top 3 recommended roles")
    cols = st.columns(3)
    for col, (_, row) in zip(cols, ranking.head(3).iterrows()):
        with col.container(border=True):
            st.metric(row["role"], f"{row['match_score']:.0f}%")
            st.caption(f"{len(row['found_required'])} of "
                       f"{len(row['found_required']) + len(row['missing_required'])} required skills")

    chart_df = ranking.sort_values("match_score").assign(
        highlight=lambda d: d["role"].eq(target_role).map({True: "Target role", False: "Other roles"})
    )
    fig = px.bar(
        chart_df, x="match_score", y="role", orientation="h", text="match_score",
        hover_data={"skill_coverage": True, "text_similarity": True, "role": False, "highlight": False},
        labels={"match_score": "Match score (%)", "role": "", "highlight": "",
                "skill_coverage": "Skill coverage (%)", "text_similarity": "Text similarity (%)"},
        color="highlight", color_discrete_map={"Target role": "#2f7de1", "Other roles": "#8fa9c9"},
        range_x=[0, 100],
    )
    fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10),
                      title="Match score for every role", legend_title_text="")
    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        ranking[["role", "match_score", "skill_coverage", "text_similarity"]].rename(columns={
            "role": "Role", "match_score": "Match score %",
            "skill_coverage": "Skill coverage %", "text_similarity": "Text similarity %",
        }),
        hide_index=True, width="stretch",
    )

# ---------- Extracted skills ----------
with tab_skills:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Skills by category")
        for category, names in sorted(analysis["skills_by_category"].items()):
            st.markdown(f"**{category}**")
            st.markdown(" ".join(f"`{n}`" for n in sorted(names)))
    with right:
        if skills:
            cat_df = pd.DataFrame(
                [(c, len(n)) for c, n in analysis["skills_by_category"].items()],
                columns=["Category", "Skills"],
            )
            fig = px.pie(cat_df, names="Category", values="Skills", hole=0.45,
                         title="Skill mix")
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")

    st.subheader("Where each skill appears")
    evidence_df = pd.DataFrame([
        {"Skill": s, "Category": info["category"], "Mentions": info["count"],
         "Sections": ", ".join(analysis["evidence"].get(s, [])) or "-",
         "Shown in projects/experience": "No" if s in analysis["weak_skills"] else "Yes"}
        for s, info in sorted(skills.items())
    ])
    if not evidence_df.empty:
        st.dataframe(evidence_df, hide_index=True, width="stretch")

    c1, c2, c3 = st.columns(3)
    c1.metric("Education", ", ".join(analysis["education"]) or "Not detected")
    years = analysis["experience_years"]
    c2.metric("Experience", f"{years} years" if years else "Not detected")
    c3.metric("Sections detected", len([s for s in analysis["sections"] if s != "header"]))
    if analysis["removed_personal_lines"]:
        st.caption(f"{analysis['removed_personal_lines']} line(s) with personal or contact "
                   "details (e.g. date of birth, gender, email) were ignored before scoring.")

# ---------- Skill gap ----------
with tab_gap:
    st.subheader(f"Skill gap for {target_role}")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.markdown("✅ **Skills found**")
        for s in target["found_required"] + target["found_nice"]:
            st.markdown(f"- {s}")
        if not (target["found_required"] or target["found_nice"]):
            st.caption("None yet")
    with g2:
        st.markdown("❌ **Missing skills**")
        for s in target["missing_required"]:
            st.markdown(f"- **{s}** (required)")
        for s in target["missing_nice"]:
            st.markdown(f"- {s} (nice to have)")
        if not (target["missing_required"] or target["missing_nice"]):
            st.caption("Nothing missing")
    with g3:
        st.markdown("⚠️ **Weak skills**")
        st.caption("Listed on the resume but not shown in any project or experience.")
        for s in target["weak"]:
            st.markdown(f"- {s}")
        if not target["weak"]:
            st.caption("None")

    total_req = len(target["found_required"]) + len(target["missing_required"])
    if total_req:
        st.progress(len(target["found_required"]) / total_req,
                    text=f"{len(target['found_required'])}/{total_req} required skills covered")
    st.info("A missing keyword does not always mean a missing ability. If you have a skill, "
            "make it visible by naming it in a project or experience bullet.")

# ---------- Roadmap ----------
with tab_roadmap:
    st.subheader(f"Suggested roadmap for {target_role}")
    for step in target["roadmap"]:
        label = ", ".join(step["skills"]) if step["skills"] else "Project"
        with st.container(border=True):
            st.markdown(f"**Week {step['week']}: {label}**")
            st.write(step["focus"])

# ---------- Report ----------
with tab_report:
    st.subheader("Download your analysis")
    pdf_bytes = build_pdf(analysis, target, filename)
    report_name = f"resume_analysis_{target_role.replace(' ', '_').replace('&', 'and')}.pdf"
    st.download_button("⬇️ Download PDF report", pdf_bytes, file_name=report_name,
                       mime="application/pdf", type="primary")
    csv = ranking.drop(columns=["found_nice", "missing_nice"]).to_csv(index=False)
    st.download_button("⬇️ Download role scores (CSV)", csv, file_name="role_scores.csv",
                       mime="text/csv")
    if st.checkbox("Also save this report in the app's reports/ folder"):
        REPORT_DIR.mkdir(exist_ok=True)
        (REPORT_DIR / report_name).write_bytes(pdf_bytes)
        st.caption(f"Saved reports/{report_name}. Only the report is saved, never the resume.")
    with st.expander("Show the cleaned resume text used for matching"):
        st.text(analysis["clean_text"])
