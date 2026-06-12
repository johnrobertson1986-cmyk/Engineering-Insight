st.header("GIS Layers and Clash Review")

left, right = st.columns([2, 1])

with right:
    st.subheader("Layer Controls")

    provider_col = "Asset Owner" if "Asset Owner" in assets.columns else None

    if provider_col:
        providers = sorted(assets[provider_col].dropna().astype(str).unique())
        selected_providers = st.multiselect(
            "Turn providers on/off",
            providers,
            default=providers
        )
    else:
        selected_providers = []

    risk_options = sorted(clean_issues["Risk"].dropna().astype(str).unique()) if "Risk" in clean_issues.columns else []
    selected_risks = st.multiselect(
        "Turn risk layers on/off",
        risk_options,
        default=risk_options
    )

    st.subheader("Clashes")
    filtered_clashes = clean_issues.copy()

    if "Risk" in filtered_clashes.columns and selected_risks:
        filtered_clashes = filtered_clashes[
            filtered_clashes["Risk"].astype(str).isin(selected_risks)
        ]

    for _, row in filtered_clashes.iterrows():
        with st.expander(f"{row.get('Issue ID','')} | {row.get('Risk','')}"):
            st.write(f"**Proposed:** {row.get('Proposed Asset','')}")
            st.write(f"**Existing:** {row.get('Existing Asset','')}")
            st.write(f"**Location:** {row.get('Location','')}")
            st.write(f"**Actual separation:** {row.get('Depth Difference (m)','')} m")
            st.write(f"**Required separation:** {row.get('Required Separation (m)','')} m")
            st.write(f"**Recommendation:** {row.get('Lesson Recommendation','')}")
            st.write(f"**Evidence:** {row.get('Evidence Required','')}")

with left:
    st.subheader("Satellite / GIS Utility Map")

    import folium
    from folium.plugins import MeasureControl
    from streamlit_folium import st_folium

    if "Latitude" in assets.columns and "Longitude" in assets.columns:

        map_assets = assets.copy()
        map_assets["Latitude"] = pd.to_numeric(map_assets["Latitude"], errors="coerce")
        map_assets["Longitude"] = pd.to_numeric(map_assets["Longitude"], errors="coerce")
        map_assets = map_assets.dropna(subset=["Latitude", "Longitude"])

        if provider_col and selected_providers:
            map_assets = map_assets[
                map_assets[provider_col].astype(str).isin(selected_providers)
            ]

        if len(map_assets) > 0:
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

            # Optional ACTmapi / ACT Government WMS placeholder.
            # Replace url/layers with exact WMS layer from ACT Geospatial Data Catalogue.
            # folium.raster_layers.WmsTileLayer(
            #     url="PASTE_ACTMAPI_WMS_URL_HERE",
            #     layers="PASTE_LAYER_NAME_HERE",
            #     name="ACTmapi Layer",
            #     fmt="image/png",
            #     transparent=True,
            #     overlay=True,
            #     control=True
            # ).add_to(m)

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
                owner = str(asset.get(provider_col, "Unknown")) if provider_col else "Unknown"

                if owner not in provider_groups:
                    provider_groups[owner] = folium.FeatureGroup(name=f"Provider: {owner}", show=True)
                    provider_groups[owner].add_to(m)

                colour = owner_colours.get(owner, "gray")

                popup = f"""
                <b>{asset.get('Asset Type','')}</b><br>
                Asset ID: {asset.get('Asset ID','')}<br>
                Owner: {owner}<br>
                Status: {asset.get('Status','')}<br>
                Depth: {asset.get('Depth (m)','')} m<br>
                Location: {asset.get('Location','')}
                """

                folium.CircleMarker(
                    location=[asset["Latitude"], asset["Longitude"]],
                    radius=7,
                    color=colour,
                    fill=True,
                    fill_color=colour,
                    fill_opacity=0.85,
                    popup=popup,
                    tooltip=f"{asset.get('Asset ID','')} | {asset.get('Asset Type','')}"
                ).add_to(provider_groups[owner])

            risk_group = folium.FeatureGroup(name="Risk / Clash Issues", show=True)
            risk_group.add_to(m)

            def find_asset(asset_name):
                if "Asset Type" not in map_assets.columns:
                    return None
                matches = map_assets[
                    map_assets["Asset Type"].astype(str).str.lower() == str(asset_name).lower()
                ]
                if len(matches) == 0:
                    return None
                return matches.iloc[0]

            for _, issue in filtered_clashes.iterrows():
                proposed = find_asset(issue.get("Proposed Asset", ""))
                existing = find_asset(issue.get("Existing Asset", ""))

                if proposed is not None and existing is not None:
                    p = [proposed["Latitude"], proposed["Longitude"]]
                    e = [existing["Latitude"], existing["Longitude"]]

                    risk = str(issue.get("Risk", ""))
                    risk_colour = "red" if risk.lower() == "high" else "orange" if risk.lower() == "medium" else "green"

                    folium.PolyLine(
                        [p, e],
                        color=risk_colour,
                        weight=5,
                        opacity=0.9,
                        tooltip=f"{issue.get('Issue ID','')} | {issue.get('Depth Difference (m)','')}m actual / {issue.get('Required Separation (m)','')}m required"
                    ).add_to(risk_group)

                    mid_lat = (p[0] + e[0]) / 2
                    mid_lon = (p[1] + e[1]) / 2

                    popup = f"""
                    <b>{issue.get('Issue ID','')} - {risk}</b><br>
                    Rule: {issue.get('Rule ID','')}<br>
                    Proposed: {issue.get('Proposed Asset','')}<br>
                    Existing: {issue.get('Existing Asset','')}<br>
                    Actual separation: {issue.get('Depth Difference (m)','')} m<br>
                    Required separation: {issue.get('Required Separation (m)','')} m<br>
                    Lesson: {issue.get('Lesson Learnt','')}<br>
                    Recommendation: {issue.get('Lesson Recommendation','')}
                    """

                    folium.Marker(
                        location=[mid_lat, mid_lon],
                        popup=popup,
                        tooltip=f"{issue.get('Issue ID','')} | {risk}",
                        icon=folium.Icon(color="red" if risk.lower() == "high" else "orange", icon="exclamation-sign")
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
                                {issue.get('Issue ID','')} | {issue.get('Depth Difference (m)','')}m / {issue.get('Required Separation (m)','')}m
                            </div>
                            """
                        )
                    ).add_to(risk_group)

            MeasureControl(
                position="topright",
                primary_length_unit="meters"
            ).add_to(m)

            folium.LayerControl(collapsed=False).add_to(m)

            st_folium(m, width=None, height=750)

        else:
            st.warning("No mapped assets available for selected providers.")
    else:
        st.warning("No Latitude / Longitude columns found in the Assets sheet.")
