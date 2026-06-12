import streamlit as st
import pandas as pd
from io import BytesIO

import folium
from folium.plugins import MeasureControl
from streamlit_folium import st_folium

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


st.set_page_config(page_title="Engineering Insight", layout="wide")

st.title("Engineering Insight")
st.subheader("Rules Engine | Utility Clearance Review | Lessons Learnt | GIS Map")

uploaded_file = st.file_uploader(
    "Upload Engineering Insight Excel workbook",
    type=["xlsx"]
)


def make_pdf(clean_issues):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "normal_wrap",
        parent=styles["Normal"],
        fontSize=8,
        leading=10
    )

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
            ["Status", str(row.get("Status", ""))],
            ["Lesson ID", str(row.get("Lesson ID", ""))],
            ["Lesson Learnt", str(row.get("Lesson Learnt", ""))],
            ["Recommendation", str(row.get("Lesson Recommendation", ""))],
            ["Evidence Required", str(row.get("Evidence Required", ""))],
            ["Source Project", str(row.get("Lesson Source Project", ""))],
            ["Next Action", str(row.get("Next Action", ""))]
        ]

        wrapped = [[Paragraph(str(a), normal), Paragraph(str(b), normal)] for a, b in data]
        table = Table(wrapped, colWidths=[130, 360])

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        story.append(table)
        story.append(Spacer(1, 18))

    doc.build(story)
    buffer.seek(0)
    return buffer


def get_asset_coords(assets, asset_name):
    if "Asset Type" not in assets.columns:
        return None

    match = assets[
        assets["Asset Type"].astype(str).str.lower()
        == str(asset_name).lower()
    ]

    if len(match) == 0:
        return None

    row = match.iloc[0]

    if "Latitude" not in row or "Longitude" not in row:
        return None

    lat = pd.to_numeric(row.get("Latitude"), errors="coerce")
    lon = pd.to_numeric(row.get("Longitude"), errors="coerce")

    if pd.isna(lat) or pd.isna(lon):
        return None

    return float(lat), float(lon)


def create_gis_map(assets, clean_issues):
    assets = assets.copy()

    assets["Latitude"] = pd.to_numeric(assets["Latitude"], errors="coerce")
    assets["Longitude"] = pd.to_numeric(assets["Longitude"], errors="coerce")

    valid_assets = assets.dropna(subset=["Latitude", "Longitude"])

    centre_lat = valid_assets["Latitude"].mean()
    centre_lon = valid_assets["Longitude"].mean()

    m = folium.Map(
        location=[centre_lat, centre_lon],
        zoom_start=17,
        tiles=None
    )

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Street Map",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="CartoDB positron",
        name="Light GIS Base",
        overlay=False,
        control=True
    ).add_to(m)

    existing_group = folium.FeatureGroup(name="Existing Assets", show=True)
    proposed_group = folium.FeatureGroup(name="Proposed Assets", show=True)
    risk_group = folium.FeatureGroup(name="High Risk Issues", show=True)

    for _, row in valid_assets.iterrows():
        status = str(row.get("Status", "")).lower()
        asset_type = str(row.get("Asset Type", "Unknown Asset"))
        asset_id = str(row.get("Asset ID", ""))
        depth = str(row.get("Depth (m)", ""))
        owner = str(row.get("Asset Owner", ""))
        location = str(row.get("Location", ""))

        popup = f"""
        <b>{asset_type}</b><br>
        Asset ID: {asset_id}<br>
        Owner: {owner}<br>
        Depth: {depth} m<br>
        Location: {location}
        """

        if "proposed" in status:
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=7,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=0.8,
                popup=popup
            ).add_to(proposed_group)
        else:
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=5,
                color="green",
                fill=True,
                fill_color="green",
                fill_opacity=0.7,
                popup=popup
            ).add_to(existing_group)

    for _, issue in clean_issues.iterrows():
        proposed = issue.get("Proposed Asset", "")
        existing = issue.get("Existing Asset", "")

        proposed_coord = get_asset_coords(assets, proposed)
        existing_coord = get_asset_coords(assets, existing)

        if proposed_coord and existing_coord:
            actual_sep = issue.get("Depth Difference (m)", "")
            required_sep = issue.get("Required Separation (m)", "")

            popup = f"""
            <b>{issue.get('Issue ID', '')} - HIGH RISK</b><br>
            Rule: {issue.get('Rule ID', '')}<br>
            Proposed: {proposed}<br>
            Existing: {existing}<br>
            Actual separation: {actual_sep} m<br>
            Required separation: {required_sep} m<br>
            Recommendation: {issue.get('Lesson Recommendation', '')}
            """

            folium.PolyLine(
                locations=[proposed_coord, existing_coord],
                color="red",
                weight=5,
                opacity=0.9,
                tooltip=f"{issue.get('Issue ID', '')}: {actual_sep}m actual / {required_sep}m required"
            ).add_to(risk_group)

            mid_lat = (proposed_coord[0] + existing_coord[0]) / 2
            mid_lon = (proposed_coord[1] + existing_coord[1]) / 2

            folium.Marker(
                location=[mid_lat, mid_lon],
                icon=folium.Icon(color="red", icon="warning-sign"),
                popup=popup
            ).add_to(risk_group)

    existing_group.add_to(m)
    proposed_group.add_to(m)
    risk_group.add_to(m)

    MeasureControl(
        position="topright",
        primary_length_unit="meters",
        secondary_length_unit="kilometers"
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m


if uploaded_file:
    excel_file = pd.ExcelFile(uploaded_file)

    required_sheets = ["Rules", "Assets", "Issues"]
    missing_sheets = [s for s in required_sheets if s not in excel_file.sheet_names]

    if missing_sheets:
        st.error(f"Missing required sheet(s): {', '.join(missing_sheets)}")
        st.stop()

    rules = pd.read_excel(uploaded_file, sheet_name="Rules")
    assets = pd.read_excel(uploaded_file, sheet_name="Assets")
    issues = pd.read_excel(uploaded_file, sheet_name="Issues")

    if "Lessons_Learnt" in excel_file.sheet_names:
        lessons = pd.read_excel(uploaded_file, sheet_name="Lessons_Learnt")
    else:
        lessons = pd.DataFrame()

    clean_issues = issues[
        issues["Issue ID"].notna() &
        issues["Proposed Asset"].notna() &
        issues["Existing Asset"].notna()
    ].copy()

    clean_issues = clean_issues.drop_duplicates(subset=["Issue ID"])

    st.success("Workbook loaded successfully.")

    st.header("Project Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rules", len(rules))
    col2.metric("Assets", len(assets))
    col3.metric("Valid Issues", len(clean_issues))
    col4.metric("Lessons", len(lessons))

    high_risk = clean_issues[
        clean_issues["Risk"].astype(str).str.lower() == "high"
    ] if "Risk" in clean_issues.columns else pd.DataFrame()

    open_issues = clean_issues[
        clean_issues["Status"].astype(str).str.lower() == "open"
    ] if "Status" in clean_issues.columns else pd.DataFrame()

    lessons_applied = clean_issues[
        clean_issues["Lesson Recommendation"].notna()
    ] if "Lesson Recommendation" in clean_issues.columns else pd.DataFrame()

    col5, col6, col7 = st.columns(3)
    col5.metric("High Risk Issues", len(high_risk))
    col6.metric("Open Issues", len(open_issues))
    col7.metric("Lessons Applied", len(lessons_applied))

    st.subheader("Risk Summary")

    if "Risk" in clean_issues.columns and len(clean_issues) > 0:
        st.bar_chart(clean_issues["Risk"].value_counts())
    else:
        st.info("No risk data available.")

    st.subheader("Satellite GIS Asset Map")

    if "Latitude" in assets.columns and "Longitude" in assets.columns:
        valid_map_assets = assets.dropna(subset=["Latitude", "Longitude"])

        if len(valid_map_assets) > 0:
            gis_map = create_gis_map(assets, clean_issues)
            st_folium(gis_map, width=None, height=650)
        else:
            st.warning("Latitude and Longitude columns exist, but no coordinate data was found.")
    else:
        st.warning("No Latitude / Longitude columns found in the Assets sheet.")

    st.caption(
        "Map points are pilot GIS coordinates. Before construction, confirm assets using survey, DBYD/BYDA plans, ACTmapi data, and potholing."
    )

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
