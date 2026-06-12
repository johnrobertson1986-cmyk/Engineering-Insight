import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.set_page_config(page_title="Engineering Insight", layout="wide")

st.title("Engineering Insight")
st.subheader("Rules Engine | Utility Clearance Review | Lessons Learnt")

uploaded_file = st.file_uploader("Upload Engineering Insight Excel workbook", type=["xlsx"])

def make_pdf(clean_issues):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Engineering Insight Compliance Report", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Total Valid Issues Found: {len(clean_issues)}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    for _, row in clean_issues.iterrows():
        story.append(Paragraph(f"Issue {row.get('Issue ID', '')}", styles["Heading2"]))

        data = [
            ["Field", "Value"],
            ["Rule ID", str(row.get("Rule ID", ""))],
            ["Proposed Asset", str(row.get("Proposed Asset", ""))],
            ["Existing Asset", str(row.get("Existing Asset", ""))],
            ["Location", str(row.get("Location", ""))],
            ["Risk", str(row.get("Risk", ""))],
            ["Proposed Depth", str(row.get("Proposed Depth (m)", ""))],
            ["Existing Depth", str(row.get("Existing Depth (m)", ""))],
            ["Actual Separation", str(row.get("Depth Difference (m)", ""))],
            ["Required Separation", str(row.get("Required Separation (m)", ""))],
            ["Recommendation", str(row.get("Lesson Recommendation", ""))],
            ["Evidence Required", str(row.get("Evidence Required", ""))],
            ["Source Project", str(row.get("Lesson Source Project", ""))]
        ]

        table = Table(data, colWidths=[120, 360])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return buffer

if uploaded_file:
    rules = pd.read_excel(uploaded_file, sheet_name="Rules")
    assets = pd.read_excel(uploaded_file, sheet_name="Assets")
    issues = pd.read_excel(uploaded_file, sheet_name="Issues")

    if "Lessons_Learnt" in pd.ExcelFile(uploaded_file).sheet_names:
        lessons = pd.read_excel(uploaded_file, sheet_name="Lessons_Learnt")
    else:
        lessons = pd.DataFrame()

    clean_issues = issues[
        issues["Issue ID"].notna() &
        issues["Proposed Asset"].notna() &
        issues["Existing Asset"].notna()
    ].copy()

    st.success("Workbook loaded successfully.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rules", len(rules))
    col2.metric("Assets", len(assets))
    col3.metric("Valid Issues", len(clean_issues))
    col4.metric("Lessons", len(lessons))

    st.subheader("Issues Register")
    st.dataframe(clean_issues, use_container_width=True)

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        rules.to_excel(writer, sheet_name="Rules", index=False)
        assets.to_excel(writer, sheet_name="Assets", index=False)
        clean_issues.to_excel(writer, sheet_name="Issues", index=False)
        if len(lessons) > 0:
            lessons.to_excel(writer, sheet_name="Lessons_Learnt", index=False)

    st.download_button(
        "Download Clean Excel Report",
        data=excel_buffer.getvalue(),
        file_name="Engineering_Insight_App_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    pdf_buffer = make_pdf(clean_issues)

    st.download_button(
        "Download PDF Compliance Report",
        data=pdf_buffer,
        file_name="Engineering_Insight_Compliance_Report.pdf",
        mime="application/pdf"
    )
else:
    st.info("Upload your Engineering Insight workbook to begin.")
