"""Builds the downloadable PDF analysis report (in memory, never saved unless the user asks)."""
from datetime import date
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = (
    "This score is an estimate for learning and guidance only. It is not a hiring "
    "decision. A missing keyword does not always mean a missing ability. Personal "
    "details such as gender, age, religion, nationality, photograph, marital status "
    "and disability are not used."
)


def _table(rows, widths):
    table = Table(rows, colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]),
    ]))
    return table


def build_pdf(analysis: dict, target: dict, filename: str) -> bytes:
    styles = getSampleStyleSheet()
    body, h2 = styles["BodyText"], styles["Heading2"]
    small = styles["BodyText"].clone("small", fontSize=8, leading=10, textColor=colors.grey)
    story = [
        Paragraph("AI Resume Analysis Report", styles["Title"]),
        Paragraph(f"Resume: {escape(filename)} &nbsp;|&nbsp; Date: {date.today():%d %b %Y}", body),
        Spacer(1, 8),
        Paragraph(f"Target role: <b>{escape(target['role'])}</b> &nbsp;&nbsp; "
                  f"Match score: <b>{target['match_score']:.0f}%</b> "
                  f"(skill coverage {target['skill_coverage']:.0f}%, "
                  f"text similarity {target['text_similarity']:.0f}%)", body),
        Spacer(1, 6),
    ]

    story.append(Paragraph("Recommended roles", h2))
    top = analysis["ranking"].head(3)
    rows = [["Rank", "Role", "Match score"]] + [
        [str(i + 1), r.role, f"{r.match_score:.0f}%"] for i, r in enumerate(top.itertuples())
    ]
    story.append(_table(rows, [2 * cm, 9 * cm, 4 * cm]))

    story.append(Paragraph("Skills found in the resume", h2))
    rows = [["Category", "Skills"]] + [
        [cat, Paragraph(escape(", ".join(sorted(skills))), body)]
        for cat, skills in sorted(analysis["skills_by_category"].items())
    ]
    story.append(_table(rows, [4.5 * cm, 11.5 * cm]))

    story.append(Paragraph(f"Skill gap for {escape(target['role'])}", h2))
    gap_rows = [
        ["Found (required)", ", ".join(target["found_required"]) or "-"],
        ["Missing (required)", ", ".join(target["missing_required"]) or "None"],
        ["Missing (nice to have)", ", ".join(target["missing_nice"]) or "None"],
        ["Weak (listed, not shown in projects/experience)", ", ".join(target["weak"]) or "None"],
    ]
    story.append(_table([["Type", "Skills"]] + [[Paragraph(a, body), Paragraph(escape(b), body)] for a, b in gap_rows],
                        [6 * cm, 10 * cm]))

    story.append(Paragraph("Learning roadmap", h2))
    rows = [["Week", "Focus"]] + [
        [f"Week {w['week']}", Paragraph(escape(w["focus"]), body)] for w in target["roadmap"]
    ]
    story.append(_table(rows, [2.5 * cm, 13.5 * cm]))

    story += [Spacer(1, 12), Paragraph(DISCLAIMER, small)]
    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                      title="AI Resume Analysis Report").build(story)
    return buffer.getvalue()
