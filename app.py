import streamlit as st
import pandas as pd
from io import BytesIO
import html

import folium
from folium.plugins import MeasureControl
from streamlit_folium import st_folium

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


st.set_page_config(page_title="Engineering Insight", layout="wide")

st.title("Engineering Insight")
st.subheader("Rules Engine | Utility Clearance Review | Lessons Learnt | GIS Risk Map")

uploaded_file = st.file_uploader(
    "Upload Engineering Insight Excel workbook",
    type=["xlsx"]
)


def make_pdf(clean_issues):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

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
            ["Rule ID", row.get("Rule ID", "")],
            ["Proposed Asset", row.get("Proposed Asset", "")],
            ["Existing Asset", row.get("Existing Asset", "")],
            ["Location", row.get("Location", "")],
            ["Risk", row.get("Risk", "")],
            ["Proposed Depth", row.get("Proposed Depth (m)", "")],
            ["Existing Depth", row.get("Existing Depth (m)", "")],
            ["Actual Separation", row.get("Depth Difference (m)", "")],
            ["Required Separation", row.get("Required Separation (m)", "")],
            ["Recommendation", row.get("Lesson Recommendation", "")],
            ["Evidence Required", row.get("Evidence Required", "")],
            ["Next Action", row.get("Next Action", "")]
        ]

        wrapped = [
            [Paragraph(str(a), normal), Paragraph(str(b), normal)]
            for a, b in data
        ]

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


def find_asset_by_type(asset_table, asset_type):
    if "Asset Type" not in asset_table.columns:
        return None

    matches = asset_table[
        asset_table["Asset Type"].astype(str).str.lower()
        == str(asset_type).lower()
    ]

    if len(matches) == 0:
        return None

    return matches.iloc[0]


def build_map(assets, clean_issues, selected_providers, selected_risks):
    map_assets = assets.copy()

    map_assets["Latitude"] = pd.to_numeric(map_assets["Latitude"], errors="coerce")
    map_assets["Longitude"] = pd.to_numeric(map_assets["Longitude"], errors="coerce")
    map_assets = map_assets.dropna(subset=["Latitude", "Longitude"])

    if "Asset Owner" in map_assets.columns and selected_providers:
        map_assets = map_assets[
            map_assets["Asset Owner"].astype(str).isin(selected_providers)
        ]

    centre_lat = map_assets["Latitude"].mean()
    centre_lon = map_assets["Longitude"].mean()

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

    owner_colours = {
        "Icon Water": "blue",
        "Evoenergy": "orange",
        "Telstra": "purple",
        "NBN": "cadetblue",
        "TCCS": "green",
        "Developer": "black",
        "Private": "gray"
    }

    provider_groups = {}

    for _, asset in map_assets.iterrows():
        owner = str(asset.get("Asset Owner", "Unknown"))

        if owner not in provider_groups:
            provider_groups[owner] = folium.FeatureGroup(
                name=f"Provider: {owner}",
                show=True
            )
            provider_groups[owner].add_to(m)

        colour = owner_colours.get(owner, "gray")

        popup = f"""
        <b>{asset.get('Asset Type', '')}</b><br>
        Asset ID: {asset.get('Asset ID', '')}<br>
        Owner: {owner}<br>
        Status: {asset.get('Status', '')}<br>
        Depth: {asset.get('Depth (m)', '')} m<br>
        Location: {asset.get('Location', '')}
        """

        folium.CircleMarker(
            location=[asset["Latitude"], asset["Longitude"]],
            radius=7,
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.85,
            popup=popup,
            tooltip=f"{asset.get('Asset ID', '')} | {asset.get('Asset Type', '')}"
        ).add_to(provider_groups[owner])

    risk_group = folium.FeatureGroup(name="Risk / Clash Issues", show=True)
    risk_group.add_to(m)

    filtered_clashes = clean_issues.copy()

    if "Risk" in filtered_clashes.columns and selected_risks:
        filtered_clashes = filtered_clashes[
            filtered_clashes["Risk"].astype(str).isin(selected_risks)
        ]

    for _, issue in filtered_clashes.iterrows():
        proposed_asset = find_asset_by_type(map_assets, issue.get("Proposed Asset", ""))
        existing_asset = find_asset_by_type(map_assets, issue.get("Existing Asset", ""))

        if proposed_asset is not None and existing_asset is not None:
            p = [proposed_asset["Latitude"], proposed_asset["Longitude"]]
            e = [existing_asset["Latitude"], existing_asset["Longitude"]]

            risk = str(issue.get("Risk", ""))

            if risk.lower() == "high":
                risk_colour = "red"
            elif risk.lower() == "medium":
                risk_colour = "orange"
            else:
                risk_colour = "green"

            actual_sep = issue.get("Depth Difference (m)", "")
            required_sep = issue.get("Required Separation (m)", "")

            folium.PolyLine(
                [p, e],
                color=risk_colour,
                weight=6,
                opacity=0.9,
                tooltip=f"{issue.get('Issue ID', '')}: {actual_sep}m actual / {required_sep}m required"
            ).add_to(risk_group)

            mid_lat = (p[0] + e[0]) / 2
            mid_lon = (p[1] + e[1]) / 2

            popup = f"""
            <b>{issue.get('Issue ID', '')} - {risk}</b><br>
            Rule: {issue.get('Rule ID', '')}<br>
            Proposed: {issue.get('Proposed Asset', '')}<br>
            Existing: {issue.get('Existing Asset', '')}<br>
            Actual separation: {actual_sep} m<br>
            Required separation: {required_sep} m<br>
            Recommendation: {issue.get('Lesson Recommendation', '')}
            """

            folium.Marker(
                location=[mid_lat, mid_lon],
                popup=popup,
                tooltip=f"{issue.get('Issue ID', '')} | {risk}",
                icon=folium.Icon(
                    color="red" if risk.lower() == "high" else "orange",
                    icon="exclamation-sign"
                )
            ).add_to(risk_group)

            folium.Marker(
                location=[mid_lat, mid_lon],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        font-size: 12px;
                        color: white;
                        background: {risk_colour};
                        padding: 4px 6px;
                        border-radius: 4px;
                        border: 1px solid white;
                        white-space: nowrap;">
                        {issue.get('Issue ID', '')} | {actual_sep}m / {required_sep}m
                    </div>
                    """
                )
            ).add_to(risk_group)

    MeasureControl(
        position="topright",
        primary_length_unit="meters"
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    return m


def render_wrapped_issues_table(clean_issues):
    st.subheader("Issues Summary")

    summary_columns = [
        "Issue ID",
        "Risk",
        "Proposed Asset",
        "Existing Asset",
        "Location",
        "Depth Difference (m)",
        "Required Separation (m)",
        "Lesson Recommendation",
        "Evidence Required",
        "Next Action"
    ]

    available_columns = [
        col for col in summary_columns
        if col in clean_issues.columns
    ]

    issues_summary = clean_issues[available_columns].copy()

    st.markdown(
        """
        <style>
        .issues-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 10px;
        }
        .issues-table th {
            background-color: #f2f2f2;
            font-weight: 700;
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            vertical-align: top;
            font-size: 13px;
        }
        .issues-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            vertical-align: top;
            white-space: normal;
            word-wrap: break-word;
            overflow-wrap: break-word;
            font-size: 13px;
            line-height: 1.35;
        }
        .issues-table tr:nth-child(even) {
            background-color: #fafafa;
        }
        .risk-high {
            color: white;
            background-color: #d62728;
            font-weight: 700;
            text-align: center;
        }
        .risk-medium {
            color: black;
            background-color: #ffbf00;
            font-weight: 700;
            text-align: center;
        }
        .risk-low {
            color: white;
            background-color: #2ca02c;
            font-weight: 700;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    table_html = "<table class='issues-table'>"
    table_html += "<tr>"

    for col in issues_summary.columns:
        table_html += f"<th>{html.escape(str(col))}</th>"

    table_html += "</tr>"

    for _, row in issues_summary.iterrows():
        table_html += "<tr>"

        for col in issues_summary.columns:
            value = row.get(col, "")

            if pd.isna(value):
                value = ""

            safe_value = html.escape(str(value))

            if col == "Risk":
                risk = str(value).lower()

                if risk == "high":
                    table_html += f"<td class='risk-high'>{safe_value}</td>"
                elif risk == "medium":
                    table_html += f"<td class='risk-medium'>{safe_value}</td>"
                elif risk == "low":
                    table_html += f"<td class='risk-low'>{safe_value}</td>"
                else:
                    table_html += f"<td>{safe_value}</td>"
            else:
                table_html += f"<td>{safe_value}</td>"

        table_html += "</tr>"

    table_html += "</table>"

    st.markdown(table_html, unsafe_allow_html=True)


if uploaded_file:
    excel_file = pd.ExcelFile(uploaded_file)

    required_sheets = ["Rules", "Assets", "Issues"]

    missing_sheets = [
        sheet for sheet in required_sheets
        if sheet not in excel_file.sheet_names
    ]

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

    if "Risk" in clean_issues.columns:
        high_risk = clean_issues[
            clean_issues["Risk"].astype(str).str.lower() == "high"
        ]
    else:
        high_risk = pd.DataFrame()

    if "Status" in clean_issues.columns:
        open_issues = clean_issues[
            clean_issues["Status"].astype(str).str.lower() == "open"
        ]
    else:
        open_issues = pd.DataFrame()

    if "Lesson Recommendation" in clean_issues.columns:
        lessons_applied = clean_issues[
            clean_issues["Lesson Recommendation"].notna()
        ]
    else:
        lessons_applied = pd.DataFrame()

    col5, col6, col7 = st.columns(3)

    col5.metric("High Risk Issues", len(high_risk))
    col6.metric("Open Issues", len(open_issues))
    col7.metric("Lessons Applied", len(lessons_applied))

    st.subheader("Risk Summary")

    if "Risk" in clean_issues.columns and len(clean_issues) > 0:
        st.bar_chart(clean_issues["Risk"].value_counts())
    else:
        st.info("No risk data available.")

    st.header("GIS Layers and Clash Review")

    if "Asset Owner" in assets.columns:
        providers = sorted(assets["Asset Owner"].dropna().astype(str).unique())
    else:
        providers = []

    if "Risk" in clean_issues.columns:
        risk_options = sorted(clean_issues["Risk"].dropna().astype(str).unique())
    else:
        risk_options = []

    left, right = st.columns([2, 1])

    with right:
        st.subheader("Layer Controls")

        selected_providers = st.multiselect(
            "Turn providers on/off",
            providers,
            default=providers
        )

        selected_risks = st.multiselect(
            "Turn risk layers on/off",
            risk_options,
            default=risk_options
        )

        st.subheader("Clashes")

        clash_box = clean_issues.copy()

        if "Risk" in clash_box.columns and selected_risks:
            clash_box = clash_box[
                clash_box["Risk"].astype(str).isin(selected_risks)
            ]

        if len(clash_box) == 0:
            st.info("No clashes found for selected filters.")

        for _, row in clash_box.iterrows():
            title = f"{row.get('Issue ID', '')} | {row.get('Risk', '')}"

            with st.expander(title):
                st.write(f"**Proposed:** {row.get('Proposed Asset', '')}")
                st.write(f"**Existing:** {row.get('Existing Asset', '')}")
                st.write(f"**Location:** {row.get('Location', '')}")
                st.write(f"**Actual separation:** {row.get('Depth Difference (m)', '')} m")
                st.write(f"**Required separation:** {row.get('Required Separation (m)', '')} m")
                st.write(f"**Recommendation:** {row.get('Lesson Recommendation', '')}")
                st.write(f"**Evidence:** {row.get('Evidence Required', '')}")

    with left:
        st.subheader("Satellite / GIS Utility Map")

        if "Latitude" in assets.columns and "Longitude" in assets.columns:
            assets_for_map = assets.copy()

            assets_for_map["Latitude"] = pd.to_numeric(
                assets_for_map["Latitude"],
                errors="coerce"
            )

            assets_for_map["Longitude"] = pd.to_numeric(
                assets_for_map["Longitude"],
                errors="coerce"
            )

            assets_for_map = assets_for_map.dropna(
                subset=["Latitude", "Longitude"]
            )

            if len(assets_for_map) > 0:
                gis_map = build_map(
                    assets_for_map,
                    clean_issues,
                    selected_providers,
                    selected_risks
                )

                st_folium(
                    gis_map,
                    width=None,
                    height=750
                )
            else:
                st.warning(
                    "Latitude and Longitude columns exist, but no valid coordinate data was found."
                )
        else:
            st.warning(
                "No Latitude / Longitude columns found in the Assets sheet."
            )

    st.caption(
        "Map points are pilot GIS coordinates. Before construction, confirm assets using survey, BYDA/DBYD plans, ACTmapi data, and potholing."
    )

    render_wrapped_issues_table(clean_issues)

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
