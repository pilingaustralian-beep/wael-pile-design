# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from inputs import Project, SoilLayer, PileGeometry, Reinforcement, Loads, DesignOptions, SoilType, PileHeadType, RockMethod
from geotechnical_pro import calculate_layered_bearing
from structural import concrete_stress_check, reinforcement_area, ultimate_axial_capacity, min_reinforcement_check, stirrup_spacing_check, generate_interaction_diagram, shear_check, crack_width_check, get_concrete_modulus
from reese_matlock import moment_and_distribution
from lateral_numerical import solve_lateral_fdm
from visuals import draw_longitudinal_section, draw_cross_section, draw_3d_pile_model
import math
import json
import os

# --- SOIL DATABASE (Professional Suite) ---
SOIL_DB = {
    "Sand": {
        "Very Loose Sand": {"gamma": 16.0, "phi": 26.0, "Nq": 20.0, "Es": 10000.0},
        "Loose Sand": {"gamma": 17.0, "phi": 29.0, "Nq": 35.0, "Es": 20000.0},
        "Medium Dense Sand": {"gamma": 18.5, "phi": 32.0, "Nq": 65.0, "Es": 35000.0},
        "Dense Sand": {"gamma": 20.0, "phi": 36.0, "Nq": 110.0, "Es": 55000.0},
        "Very Dense Sand": {"gamma": 21.0, "phi": 41.0, "Nq": 160.0, "Es": 80000.0},
    },
    "Clay": {
        "Very Soft Clay": {"gamma": 15.0, "Cu": 15.0, "alpha": 1.0, "Es": 3000.0},
        "Soft Clay": {"gamma": 16.5, "Cu": 30.0, "alpha": 0.85, "Es": 8000.0},
        "Medium Clay": {"gamma": 18.0, "Cu": 60.0, "alpha": 0.65, "Es": 18000.0},
        "Stiff Clay": {"gamma": 19.5, "Cu": 120.0, "alpha": 0.45, "Es": 35000.0},
        "Very Stiff Clay": {"gamma": 20.5, "Cu": 200.0, "alpha": 0.35, "Es": 60000.0},
    },
    "Rock": {
        "Highly Weathered Rock": {"gamma": 21.0, "quc": 2.0, "Nc": 8.0, "alpha_rock": 0.1, "RQD": 0.2},
        "Weak Rock (Marl/Shale)": {"gamma": 23.0, "quc": 10.0, "Nc": 15.0, "alpha_rock": 0.25, "RQD": 0.45},
        "Medium Hard Rock": {"gamma": 24.5, "quc": 25.0, "Nc": 30.0, "alpha_rock": 0.4, "RQD": 0.7},
        "Hard Rock (Limestone)": {"gamma": 26.0, "quc": 60.0, "Nc": 50.0, "alpha_rock": 0.55, "RQD": 0.9},
    }
}

# Page Config
st.set_page_config(page_title="Pile Design Suite Pro", layout="wide", page_icon="🏗️")

# --- CUSTOM CSS FOR PRINTING ---
st.markdown("""
    <style>
    @media print {
        header, [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"], .stTabs [role="tablist"] {
            display: none !important;
        }
        .main .block-container {
            padding: 5mm !important;
            max-width: 100% !important;
        }
        .stPlotlyChart {
            page-break-inside: avoid !important;
            height: 800px !important;
            width: 100% !important;
        }
        iframe {
            height: 800px !important;
            width: 100% !important;
            border: none !important;
        }
        [data-testid="stAppViewContainer"], .main, .block-container {
            overflow: visible !important;
            height: auto !important;
        }
        .print-table {
            width: 100%;
            border-collapse: collapse;
            margin: 0 !important;
            margin-bottom: 10px !important;
        }
        .stPlotlyChart {
            margin-top: -30px !important;
            margin-bottom: -30px !important;
        }
        .dev-signature {
            display: none !important;
        }
        }
        .print-table th, .print-table td {
            border: 1px solid black !important;
            padding: 8px;
            text-align: left;
            font-size: 12px;
            color: black !important;
        }
        .print-table th {
            background-color: #f2f2f2 !important;
            -webkit-print-color-adjust: exact;
        }
        .section-header {
            background-color: #333 !important;
            color: white !important;
            padding: 5px 10px;
            margin-top: 20px;
            -webkit-print-color-adjust: exact;
        }
        .print-page-break {
            page-break-before: always !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- 1. Session State Initialization ---
initial_values = {
    "proj_name": "تصميم بايل",
    "job_no": "J-2026-001",
    "owner": "المالك",
    "consultant": "ABC Engineering",
    "contractor": "XYZ Construction",
    "dia": 500.0,
    "length": 10.2,
    "cut_off": -1.0,
    "ground_lvl": 0.0,
    "gwt": -3.0,
    "p_vertical": 1000.0,
    "p_horizontal": 0.0,
    "allowable_deflection": 25.0,
    "fcu": 40.0,
    "fy": 460.0,
    "bar_dia": 16,
    "bar_num": 6,
    "stirrup_dia": 8,
    "stirrup_sp": 150,
    "layers_df": pd.DataFrame([
        {"Name": "Fill", "Type": "رمل", "Top Depth": 0.0, "Bottom Depth": 2.0, "Gamma": 17.0, "Phi/Cu/quc": 28.0, "Nq/Alpha/Nc": 50.0, "Es": 15000.0, "alpha_rock": np.nan, "RQD": np.nan},
        {"Name": "Medium Clay", "Type": "طين", "Top Depth": 2.0, "Bottom Depth": 5.0, "Gamma": 18.0, "Phi/Cu/quc": 60.0, "Nq/Alpha/Nc": 0.65, "Es": 18000.0, "alpha_rock": 0.4, "RQD": 0.5},
        {"Name": "Medium Hard Rock", "Type": "صخر", "Top Depth": 5.0, "Bottom Depth": 30.0, "Gamma": 24.5, "Phi/Cu/quc": 25.0, "Nq/Alpha/Nc": 30.0, "Es": 25000.0, "alpha_rock": 0.4, "RQD": 0.7}
    ]),
    "socket_mode": True,
    "fos_geotech": 2.5,
    "nh": 5.0   # NEW: Subgrade modulus (MN/m³)
}

for key, val in initial_values.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 2. Helper Functions ---
def sync_data(data):
    if "project" in data:
        st.session_state.proj_name = data["project"].get("name", initial_values["proj_name"])
        st.session_state.job_no = data["project"].get("job_no", initial_values["job_no"])
        st.session_state.owner = data["project"].get("owner", initial_values["owner"])
        st.session_state.consultant = data["project"].get("consultant", initial_values["consultant"])
        st.session_state.contractor = data["project"].get("contractor", initial_values["contractor"])
    if "settings" in data:
        st.session_state.socket_mode = data["settings"].get("socket_mode", False)
        st.session_state.fos_geotech = data["settings"].get("fos_geotech", 2.5)
        st.session_state.nh = data["settings"].get("nh", 5.0)
    if "geometry" in data:
        st.session_state.dia = float(data["geometry"].get("dia", initial_values["dia"]))
        st.session_state.length = float(data["geometry"].get("length", initial_values["length"]))
        st.session_state.cut_off = float(data["geometry"].get("cut_off", initial_values["cut_off"]))
        st.session_state.ground_lvl = float(data["geometry"].get("ground_lvl", initial_values["ground_lvl"]))
        st.session_state.gwt = float(data["geometry"].get("gwt", initial_values["gwt"]))
    if "loads" in data:
        st.session_state.p_vertical = float(data["loads"].get("p_vertical", initial_values["p_vertical"]))
        st.session_state.p_horizontal = float(data["loads"].get("p_horizontal", initial_values["p_horizontal"]))
        st.session_state.allowable_deflection = float(data["loads"].get("allowable_deflection", initial_values["allowable_deflection"]))
        st.session_state.fcu = float(data["loads"].get("fcu", initial_values["fcu"]))
        st.session_state.fy = float(data["loads"].get("fy", initial_values["fy"]))
    if "reinf" in data:
        st.session_state.bar_dia = int(data["reinf"].get("bar_dia", initial_values["bar_dia"]))
        st.session_state.bar_num = int(data["reinf"].get("bar_num", initial_values["bar_num"]))
        st.session_state.stirrup_dia = int(data["reinf"].get("stirrup_dia", initial_values["stirrup_dia"]))
        st.session_state.stirrup_sp = int(data["reinf"].get("stirrup_sp", initial_values["stirrup_sp"]))
    if "layers" in data:
        st.session_state.layers_df = pd.DataFrame(data["layers"])
        if "soil_editor" in st.session_state:
            del st.session_state["soil_editor"]

def load_project(uploaded_file):
    if uploaded_file:
        try:
            content = uploaded_file.read().decode("utf-8")
            if not content.strip():
                st.error("❌ The selected file is empty.")
                return
            data = json.loads(content)
            sync_data(data)
            st.success("✅ Project data synchronized! Please wait for refresh...")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error decoding file: {e}")

def get_download_data():
    data = {
        "project": {"name": st.session_state.proj_name, "job_no": st.session_state.job_no, "owner": st.session_state.owner, "consultant": st.session_state.consultant, "contractor": st.session_state.contractor},
        "geometry": {"dia": st.session_state.dia, "length": st.session_state.length, "cut_off": st.session_state.cut_off, "ground_lvl": st.session_state.ground_lvl, "gwt": st.session_state.gwt},
        "loads": {"p_vertical": st.session_state.p_vertical, "p_horizontal": st.session_state.p_horizontal, "allowable_deflection": st.session_state.allowable_deflection, "fcu": st.session_state.fcu, "fy": st.session_state.fy},
        "reinf": {"bar_dia": st.session_state.bar_dia, "bar_num": st.session_state.bar_num, "stirrup_dia": st.session_state.stirrup_dia, "stirrup_sp": st.session_state.stirrup_sp},
        "settings": {"socket_mode": st.session_state.socket_mode, "fos_geotech": st.session_state.fos_geotech, "nh": st.session_state.nh},
        "layers": st.session_state.layers_df.to_dict(orient="records")
    }
    return json.dumps(data, indent=4)

# --- 3. Sidebar Layout ---
st.sidebar.title("🏗️ Pile Design Pro")

st.sidebar.subheader("📁 Project Management")
uploaded_file = st.sidebar.file_uploader("Upload Project File (.json)", type=["json"])
if uploaded_file:
    if st.sidebar.button("🚀 Import This Project"):
        load_project(uploaded_file)

st.sidebar.divider()
st.sidebar.subheader("⚙️ Global Design Options")
st.sidebar.checkbox("Socket Analysis Mode", key="socket_mode", help="Ignore skin friction for all layers above the first rock layer.")
st.sidebar.number_input("Geotech Factor of Safety (FoS)", 1.5, 5.0, key="fos_geotech")
st.sidebar.number_input("Subgrade Modulus nh (MN/m³)", 0.5, 50.0, key="nh", help="Used in lateral analysis for sand. Typical values: 2-5 (loose), 5-15 (medium), 15-40 (dense)")

st.sidebar.divider()
st.sidebar.text_input("Project Name", key="proj_name")
st.sidebar.text_input("Job Number", key="job_no")
st.sidebar.text_input("Owner", key="owner")
st.sidebar.text_input("Consultant", key="consultant")
st.sidebar.text_input("Contractor", key="contractor")

st.sidebar.divider()
st.sidebar.download_button(
    label="💾 Download Current Project",
    data=get_download_data(),
    file_name=f"Project_{st.session_state.proj_name.replace(' ', '_')}.json",
    mime="application/json"
)

# --- Developer Signature ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div class="dev-signature" style="text-align: center; padding: 10px; border-top: 1px solid #eee; margin-top: 20px;">
        <p style="margin: 0; color: #666; font-size: 0.8em;">Developed by:</p>
            <p style="margin: 0; color: #1e3a8a; font-weight: bold; font-size: 1.1em;">Eng. Wael Radwan</p>
            <p style="margin: 0; color: #d32f2f; font-weight: bold; font-size: 0.9em;">VERSION 2.3.1</p>
            <p style="margin: 0; color: #999; font-size: 0.75em;">P-Delta + Ks Fix + nh Control</p>
    </div>
    """,
    unsafe_allow_html=True
)

# --- 4. Main Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 General & Loads", "🌱 Soil Profile", "🧪 Borehole Wizard", "📊 Analysis", "📜 Report"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Pile Geometry")
        st.number_input("Diameter (mm)", 300, 3000, key="dia")
        st.number_input("Pile Length (m)", 5.0, 100.0, key="length")
        st.number_input("Cut-off Level (m)", -50.0, 50.0, key="cut_off")
        st.number_input("Ground Level (m)", -50.0, 50.0, key="ground_lvl")
        st.number_input("Water Table (m)", -100.0, 50.0, key="gwt")
    with col2:
        st.subheader("Loads & Materials")
        st.number_input("Working Vertical Load (kN)", 0.0, 50000.0, key="p_vertical")
        st.number_input("Horizontal Load (kN) [0 for auto 3%]", 0.0, 5000.0, key="p_horizontal")
        st.number_input("Allowable Lateral Deflection (mm)", 1.0, 100.0, key="allowable_deflection")
        st.number_input("Concrete Grade fcu (N/mm²)", 20.0, 100.0, key="fcu")
        st.number_input("Steel Grade fy (N/mm²)", 250.0, 600.0, key="fy")
    
    st.subheader("Geotechnical Summary")
    if st.session_state.socket_mode:
        st.warning("⚠️ **Socket Analysis Mode ACTIVE**: Skin friction is ignored for all layers above the first rock layer.")
    else:
        st.info("ℹ️ **Full Friction Mode**: Skin friction is calculated for all soil and rock layers.")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.number_input("Bar Dia (mm)", 8, 40, key="bar_dia")
    c2.number_input("Number of Bars", 4, 100, key="bar_num")
    c3.number_input("Link Dia (mm)", 6, 16, key="stirrup_dia")
    c4.number_input("Link Spacing (mm)", 50, 400, key="stirrup_sp")

with tab2:
    st.subheader(f"Soil Stratigraphy & Library (Items: {len(SOIL_DB)})")
    
    col_lib1, col_lib2, col_lib3 = st.columns([1, 1, 1])
    categories = list(SOIL_DB.keys())
    with col_lib1:
        lib_cat = st.selectbox("Soil Category", categories if categories else ["None"])
    with col_lib2:
        db_options = SOIL_DB.get(lib_cat, {})
        if db_options:
            lib_type = st.selectbox("Soil Type", list(db_options.keys()))
        else:
            lib_type = st.selectbox("Soil Type", ["No data"], key="no_data_select")
    with col_lib3:
        if st.button("➕ Add Layer from Library") and lib_type != "No data":
            props = SOIL_DB[lib_cat][lib_type]
            if lib_cat == "Sand":
                stype, val1, val2 = "رمل", props["phi"], props["Nq"]
            elif lib_cat == "Clay":
                stype, val1, val2 = "طين", props["Cu"], props["alpha"]
            else:
                stype, val1, val2 = "صخر", props["quc"], props["Nc"]
            
            new_row = {
                "Name": lib_type,
                "Type": stype,
                "Top Depth": 0.0, "Bottom Depth": 5.0,
                "Gamma": props["gamma"],
                "Phi/Cu/quc": val1,
                "Nq/Alpha/Nc": val2,
                "Es": props.get("Es", 25000.0),
                "alpha_rock": props.get("alpha_rock", 0.4),
                "RQD": props.get("RQD", 0.5)
            }
            st.session_state.layers_df = pd.concat([st.session_state.layers_df, pd.DataFrame([new_row])], ignore_index=True)
            st.rerun()

    st.info("💡 Tip: You can edit values directly in the table. RQD can be entered as 0.85 or 85.")
    edited_df = st.data_editor(st.session_state.layers_df, num_rows="dynamic", use_container_width=True, key="soil_editor")
    if not edited_df.equals(st.session_state.layers_df):
        st.session_state.layers_df = edited_df
        st.rerun()

    st.subheader("🔢 SPT Integration (Automation)")
    c_spt1, c_spt2, c_spt3 = st.columns(3)
    spt_n = c_spt1.number_input("SPT N-Value", 0, 100, 20)
    spt_type = c_spt2.selectbox("Calculate for", ["Sand", "Clay"])
    if c_spt3.button("Apply SPT Correlation"):
        if spt_type == "Sand":
            phi_calc = 28 + 0.4 * spt_n
            nq_calc = 2 * spt_n + 10 
            st.success(f"Calculated: Phi={phi_calc}°, Nq={nq_calc}")
        else:
            cu_calc = 6.25 * spt_n
            alpha_calc = 0.5 if cu_calc > 50 else 0.8
            st.success(f"Calculated: Cu={cu_calc} kPa, Alpha={alpha_calc}")

with tab3:
    st.header("🧪 Borehole Import Wizard")
    st.markdown("Upload your borehole Excel file and map the columns to our system.")
    
    uploaded_file = st.file_uploader("Upload Excel Borehole Log", type=["xlsx", "xls"])
    
    if uploaded_file:
        try:
            bh_df = pd.read_excel(uploaded_file)
            st.write("📋 **File Preview (Top 5 Rows):**")
            st.dataframe(bh_df.head(), use_container_width=True)
            
            cols = bh_df.columns.tolist()
            
            st.divider()
            st.subheader("🔗 Column Mapping")
            m1, m2 = st.columns(2)
            
            with m1:
                map_name = st.selectbox("Layer Name Column", cols)
                map_type = st.selectbox("Soil Type Column", cols, index=1 if len(cols)>1 else 0)
                map_top = st.selectbox("Top Depth Column", cols, index=2 if len(cols)>2 else 0)
                map_bot = st.selectbox("Bottom Depth Column", cols, index=3 if len(cols)>3 else 0)
            
            with m2:
                map_gamma = st.selectbox("Unit Weight (Gamma) Column", cols, index=4 if len(cols)>4 else 0)
                map_param = st.selectbox("Strength Param (Phi/Cu/quc) Column", cols, index=5 if len(cols)>5 else 0)
                map_rqd = st.selectbox("RQD Column (Optional)", ["None"] + cols)
                map_es = st.selectbox("Elastic Modulus Es Column (Optional)", ["None"] + cols)

            if st.button("🚀 Import Data to Profile"):
                new_rows = []
                for _, r in bh_df.iterrows():
                    stype_str = str(r[map_type]).lower()
                    if "sand" in stype_str or "رمل" in stype_str: stype = "رمل"
                    elif "clay" in stype_str or "طين" in stype_str: stype = "طين"
                    else: stype = "صخر"
                    
                    new_rows.append({
                        "Name": r[map_name],
                        "Type": stype,
                        "Top Depth": float(r[map_top]),
                        "Bottom Depth": float(r[map_bot]),
                        "Gamma": float(r[map_gamma]),
                        "Phi/Cu/quc": float(r[map_param]),
                        "Nq/Alpha/Nc": 100.0 if stype=="رمل" else (0.5 if stype=="طين" else 9.0),
                        "Es": float(r[map_es]) if map_es != "None" else 25000.0,
                        "alpha_rock": 0.4,
                        "RQD": float(r[map_rqd]) if map_rqd != "None" else 0.5
                    })
                
                st.session_state.layers_df = pd.DataFrame(new_rows)
                st.success(f"Successfully imported {len(new_rows)} layers!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Error reading file: {e}")

with tab4:
    dia = st.session_state.dia
    length = st.session_state.length
    cut_off = st.session_state.cut_off
    ground_lvl = st.session_state.ground_lvl
    gwt = st.session_state.gwt
    p_vertical = st.session_state.p_vertical
    p_horizontal = st.session_state.p_horizontal
    allowable_deflection = st.session_state.allowable_deflection
    fcu = st.session_state.fcu
    fy = st.session_state.fy
    bar_dia = st.session_state.bar_dia
    bar_num = st.session_state.bar_num
    stirrup_dia = st.session_state.stirrup_dia
    stirrup_sp = st.session_state.stirrup_sp

    st.subheader("Analysis & Visualization")
    if st.session_state.socket_mode:
        st.warning("⚠️ Socket Analysis Mode is ACTIVE.")
    
    # Basic validation
    validation_warnings = []
    if dia < 300 or dia > 3000:
        validation_warnings.append("Diameter outside typical range (300-3000 mm)")
    if length < 3:
        validation_warnings.append("Pile length is very short")
    if p_vertical <= 0:
        validation_warnings.append("Vertical load is zero or negative")
    if fcu < 20 or fcu > 100:
        validation_warnings.append("Concrete grade outside common range")
    if validation_warnings:
        for w in validation_warnings:
            st.warning(f"⚠️ {w}")
    
    pile = PileGeometry(diameter=dia, pile_length=length, cut_off_level=cut_off, ground_level=ground_lvl, gwt_level=gwt)
    loads = Loads(working_vertical=p_vertical, horizontal=p_horizontal)
    options = DesignOptions(
        fcu=fcu, 
        fy=fy, 
        E_concrete=get_concrete_modulus(fcu), 
        fos_geotech=st.session_state.fos_geotech,
        nh=st.session_state.nh
    )
    reinf = Reinforcement(bar_diameter=bar_dia, num_bars=bar_num, stirrup_diameter=stirrup_dia, stirrup_spacing=stirrup_sp)
    
    layers = []
    socket_mode = st.session_state.socket_mode
    first_rock_found = False
    
    try:
        current_layers_df = st.session_state.layers_df
    except:
        current_layers_df = pd.DataFrame(initial_values["layers_df"])

    for _, row in current_layers_df.iterrows():
        if row["Type"] == "رمل": stype = SoilType.SAND
        elif row["Type"] == "طين": stype = SoilType.CLAY
        else: stype = SoilType.ROCK
        
        ignore_friction = False
        if socket_mode:
            if stype == SoilType.ROCK:
                first_rock_found = True
            if not first_rock_found: 
                ignore_friction = True 

        RQD_raw = row.get("RQD")
        if pd.isna(RQD_raw):
            RQD_final = 0.5
        else:
            try:
                RQD_val = float(RQD_raw)
                RQD_final = RQD_val / 100.0 if RQD_val > 1.0 else RQD_val
            except:
                RQD_final = 0.5
        
        if stype == SoilType.SAND:
            phi_val = float(row["Phi/Cu/quc"]) if pd.notna(row.get("Phi/Cu/quc")) else 30.0
            Ks_val = max(0.3, min(1.0, 1.0 - math.sin(math.radians(phi_val))))
        else:
            Ks_val = 1.0

        layer = SoilLayer(
            name=str(row.get("Name", "Layer")), 
            soil_type=stype, 
            depth_top=float(row["Top Depth"]) if pd.notna(row.get("Top Depth")) else 0.0, 
            depth_bottom=float(row["Bottom Depth"]) if pd.notna(row.get("Bottom Depth")) else 0.0,
            gamma=float(row["Gamma"]) if pd.notna(row.get("Gamma")) else 18.0, 
            phi=float(row["Phi/Cu/quc"]) if stype == SoilType.SAND and pd.notna(row.get("Phi/Cu/quc")) else 30.0,
            Cu=float(row["Phi/Cu/quc"]) if stype == SoilType.CLAY and pd.notna(row.get("Phi/Cu/quc")) else 50.0,
            quc=float(row["Phi/Cu/quc"]) if stype == SoilType.ROCK and pd.notna(row.get("Phi/Cu/quc")) else 10.0,
            Es=float(row["Es"]) if pd.notna(row.get("Es")) else 25000.0,
            rock_reduction_factor=float(row["alpha_rock"]) if pd.notna(row.get("alpha_rock")) else 0.4,
            RQD=RQD_final,
            ignore_skin_friction=ignore_friction,
            Nq=float(row["Nq/Alpha/Nc"]) if stype == SoilType.SAND and pd.notna(row.get("Nq/Alpha/Nc")) else 100.0,
            alpha=float(row["Nq/Alpha/Nc"]) if stype == SoilType.CLAY and pd.notna(row.get("Nq/Alpha/Nc")) else 0.5,
            Nc=float(row["Nq/Alpha/Nc"]) if stype != SoilType.SAND and pd.notna(row.get("Nq/Alpha/Nc")) else 9.0,
            Ks=Ks_val
        )
        layers.append(layer)
    
    if not layers:
        st.error("No soil layers defined. Please add soil layers in the 'Soil Profile' tab.")
    else:
        geo_res = calculate_layered_bearing(layers, pile, loads, options)
        Ac = math.pi * dia**2 / 4.0
        Asc = reinforcement_area(bar_dia, bar_num)
        fc, fa, conc_ok = concrete_stress_check(Ac, p_vertical, fcu)
        N_ult = ultimate_axial_capacity(Ac, Asc, fcu, fy)
        
        analysis_method = st.radio("Lateral Analysis Method", ["Simplified (Reese-Matlock)", "Numerical (Finite Difference)"], horizontal=True, key="lateral_method_choice")
        if analysis_method == "Simplified (Reese-Matlock)":
            T_val, Zmax, curve, Mmax = moment_and_distribution(pile, loads, options)
            z_graph, m_graph, y_graph, v_graph = [c[0] for c in curve], [c[1] for c in curve], [c[2] for c in curve], [c[3] for c in curve]
            main_type = layers[0].soil_type if layers else SoilType.SAND
            label_stiff = "Characteristic Length (R)" if main_type == SoilType.CLAY else "Stiffness Factor (T)"
        else:
            z_graph, y_graph, moments, shears, Mmax = solve_lateral_fdm(pile, layers, loads, options)
            m_graph, y_graph, v_graph = moments.tolist(), y_graph.tolist(), shears.tolist()
            main_type = layers[0].soil_type if layers else SoilType.SAND
            D_m = dia/1000.0
            I_m4 = math.pi * D_m**4 / 64.0
            EI = options.E_concrete * 1000 * I_m4
            
            if main_type == SoilType.CLAY:
                label_stiff = "Characteristic Length (R)"
                k_val = layers[0].Cu * 20
                T_val = (EI / (k_val if k_val > 0 else 1.0))**0.25
            else:
                label_stiff = "Stiffness Factor (T)"
                T_val = (EI / (options.nh if options.nh > 0 else 1.0))**0.2

        rho_prov, rho_req, rho_ok = min_reinforcement_check(Ac, Asc, dia, p_vertical, Mmax, fcu, fy)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Geotech FoS", f"{geo_res.get('FoS', 0):.2f}", delta="Safe" if geo_res.get('FoS', 0) >= st.session_state.fos_geotech else "Unsafe")
        m2.metric("Safe Comp (kN)", f"{geo_res.get('Qall', 0):.0f}")
        m3.metric("Safe Tens (kN)", f"{geo_res.get('Qall_tens', 0):.0f}")
        m4.metric("Settlement (mm)", f"{geo_res.get('Settlement', 0):.1f}")

        st.info(f"ℹ️ **Engineering Note:** Includes GWT effects, Critical Depth (z_c = {15*dia/1000:.1f}m), **P-Δ effect** in numerical method, and user-defined nh = {st.session_state.nh} MN/m³.")

        st.write("---")
        st.subheader("Visual Analysis")
        c_sch1, c_res_sch2 = st.columns(2)
        with c_sch1: st.plotly_chart(draw_longitudinal_section(pile, layers, reinf), use_container_width=True, key="sch_long_analysis")
        with c_res_sch2: st.plotly_chart(draw_cross_section(pile, reinf), use_container_width=True, key="sch_cross_analysis")

        g1, g2, g3 = st.columns(3)
        with g1:
            fig_m = px.line(x=m_graph, y=z_graph, labels={'x': 'Moment (kNm)', 'y': 'Depth (m)'}, title="Moment Diagram")
            fig_m.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_m, use_container_width=True, key="graph_moment_analysis")
        with g2:
            fig_v = px.line(x=v_graph, y=z_graph, labels={'x': 'Shear (kN)', 'y': 'Depth (m)'}, title="Shear Force Diagram")
            fig_v.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_v, use_container_width=True, key="graph_shear_analysis")
        with g3:
            fig_y = px.line(x=y_graph, y=z_graph, labels={'x': 'Deflection (mm)', 'y': 'Depth (m)'}, title="Displacement Diagram")
            fig_y.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_y, use_container_width=True, key="graph_disp_analysis")

        st.write("---")
        N_pts, M_pts = generate_interaction_diagram(dia, fcu, fy, bar_num, bar_dia, pile.cover)
        fig_nm = go.Figure()
        fig_nm.add_trace(go.Scatter(x=M_pts, y=N_pts, name="Capacity Envelope", line=dict(color='red', dash='dash')))
        fig_nm.add_trace(go.Scatter(x=[Mmax], y=[p_vertical], name="Design Point", mode='markers', marker=dict(size=12, color='blue')))
        fig_nm.update_layout(xaxis_title="Moment M (kNm)", yaxis_title="Axial Load N (kN)", title="N-M Interaction Diagram")
        st.plotly_chart(fig_nm, use_container_width=True, key="graph_nm_analysis")

        st.divider()
        st.subheader("🧊 3D Model Visualization")
        fig_3d = draw_3d_pile_model(pile, layers)
        st.plotly_chart(fig_3d, use_container_width=True, key="graph_3d_analysis")

with tab5:
    report_container = st.container()
    with report_container:
        st.title(f"PILE DESIGN REPORT: {st.session_state.proj_name}")
        if st.session_state.socket_mode:
            st.warning("⚠️ Calculation Method: Socket Analysis Mode (Skin friction ignored above rock)")
        else:
            st.info("ℹ️ Calculation Method: Full Friction Mode")
        
        st.markdown(f"**Job No:** {st.session_state.job_no} | **Owner:** {st.session_state.owner}")
        st.markdown(f"**Consultant:** {st.session_state.consultant} | **Contractor:** {st.session_state.contractor}")
        st.markdown('<div class="section-header">1. PROJECT INFORMATION & INPUT DATA</div>', unsafe_allow_html=True)
        
        proj_html = f"""
        <table class="print-table">
            <tr><th>Project Name</th><td>{st.session_state.proj_name}</td><th>Job Number</th><td>{st.session_state.job_no}</td></tr>
            <tr><th>Owner</th><td>{st.session_state.owner}</td><th>Consultant</th><td>{st.session_state.consultant}</td></tr>
            <tr><th>Contractor</th><td>{st.session_state.contractor}</td><th>Date</th><td>{pd.Timestamp.now().strftime('%Y-%m-%d')}</td></tr>
        </table>
        """
        st.markdown(proj_html, unsafe_allow_html=True)

        col_in1, col_in2 = st.columns([1, 1.5])
        with col_in1:
            st.markdown("**Pile & Material Properties**")
            param_html = f"""
            <table class="print-table">
                <tr><th>Diameter</th><td>{dia} mm</td></tr>
                <tr><th>Length</th><td>{length} m</td></tr>
                <tr><th>Concrete fcu</th><td>{fcu} MPa</td></tr>
                <tr><th>Steel fy</th><td>{fy} MPa</td></tr>
                <tr><th>Factor of Safety</th><td>{options.fos_geotech}</td></tr>
                <tr><th>nh (Subgrade)</th><td>{options.nh} MN/m³</td></tr>
            </table>
            """
            st.markdown(param_html, unsafe_allow_html=True)
        with col_in2:
            st.markdown("**Soil Stratigraphy**")
            soil_html = "<table class='print-table'><tr><th>Name</th><th>Type</th><th>Top (m)</th><th>Base (m)</th><th>γ (kN/m³)</th></tr>"
            for _, r in st.session_state.layers_df.iterrows():
                soil_html += f"<tr><td>{r['Name']}</td><td>{r['Type']}</td><td>{r['Top Depth']}</td><td>{r['Bottom Depth']}</td><td>{r['Gamma']}</td></tr>"
            soil_html += "</table>"
            st.markdown(soil_html, unsafe_allow_html=True)

        st.markdown("**Schematics**")
        st.markdown('<div class="print-page-break"></div>', unsafe_allow_html=True)
        c_rep_sch1, c_rep_sch2 = st.columns([1.5, 1])
        with c_rep_sch1: st.plotly_chart(draw_longitudinal_section(pile, layers, reinf), use_container_width=True, key="sch_long_report")
        with c_rep_sch2: st.plotly_chart(draw_cross_section(pile, reinf), use_container_width=True, key="sch_cross_report")

        st.markdown('<div class="section-header">2. GEOTECHNICAL ANALYSIS RESULTS</div>', unsafe_allow_html=True)
        c_res1, c_res2, c_res3, c_res4 = st.columns(4)
        c_res1.metric("Ult. Compression (Qu)", f"{geo_res.get('Qu', 0):.1f} kN")
        c_res2.metric("Safe Compression (Qall)", f"{geo_res.get('Qall', 0):.1f} kN")
        c_res3.metric("Ult. Tension (Qu_t)", f"{geo_res.get('Qu_tens', 0):.1f} kN")
        c_res4.metric("Safe Tension (Qall_t)", f"{geo_res.get('Qall_tens', 0):.1f} kN")
        
        with st.expander("📝 Detailed Geotechnical Calculations", expanded=True):
            st.markdown("**A. Shaft Friction (Qs):**")
            st.markdown(f"Total Effective Shaft Area = π * D * L_eff = π * {pile.diameter/1000} * {geo_res.get('L_eff', 0):.2f} = **{geo_res.get('As_eff', 0):.2f} m²**")
            if "Segments" in geo_res and isinstance(geo_res["Segments"], list):
                 st.table(pd.DataFrame(geo_res["Segments"]))
            else:
                 st.write("No detailed segment data available.")
            st.markdown(f"**ΣQs = {geo_res.get('Qs', 0):.2f} kN**")
            
            st.markdown("**B. Toe Bearing (Qb):**")
            st.markdown(f"Toe Area (Ab) = π * D² / 4 = {math.pi*(pile.diameter/1000)**2/4:.4f} m²")
            st.code(geo_res.get("ToeNote", "No toe note available."))
            st.markdown(f"**Qb = {geo_res.get('Qb', 0):.2f} kN**")
            
            st.markdown("**C. Total Capacity:**")
            st.markdown(f"Qu = Qs + Qb = {geo_res.get('Qs', 0):.2f} + {geo_res.get('Qb', 0):.2f} = **{geo_res.get('Qu', 0):.2f} kN**")
            st.markdown(f"Qall = Qu / FoS_req = {geo_res.get('Qu', 0):.2f} / {options.fos_geotech} = **{geo_res.get('Qall', 0):.2f} kN**")

            st.markdown("---")
            st.markdown("**D. Tension/Uplift Capacity:**")
            st.write(f"- Ultimate Tension (Qu_t) = ΣQs = **{geo_res.get('Qu_tens', 0):.2f} kN**")
            st.write(f"- Safe Tension (Qall_t) = Qu_t / (FoS_geo * 1.5) = **{geo_res.get('Qall_tens', 0):.2f} kN**")
            
            st.markdown("---")
            st.markdown("**E. Settlement Analysis (Serviceability) - Improved v2.3:**")
            st.write(f"- **Total Settlement (St) = {geo_res.get('Settlement', 0):.2f} mm**")
            st.write(f"  - s1 (Elastic shortening) = {geo_res.get('Settlement_s1', 0):.2f} mm")
            st.write(f"  - s2 (Tip settlement) = {geo_res.get('Settlement_s2', 0):.2f} mm")
            st.write(f"  - s3 (Shaft contribution) = {geo_res.get('Settlement_s3', 0):.2f} mm")
            st.write(f"- Average Es used = {geo_res.get('avg_Es', 0):.0f} kPa")

        st.markdown("**Lateral Performance Curves**")
        with st.expander("🔬 Lateral Analysis Technical Note"):
            st.info("**Governing Equation (with P-Δ):**")
            st.latex(r"EI \frac{d^4y}{dz^4} + P \frac{d^2y}{dz^2} + E_s(z) y = 0")
            D_m = dia/1000.0
            I_m4 = math.pi * D_m**4 / 64.0
            Ec_mpa = get_concrete_modulus(fcu)
            EI_val = Ec_mpa * 1000 * I_m4
            st.markdown(f"""
            **Adopted Parameters:**
            - **Concrete Modulus ($E_c$):** {Ec_mpa/1000:.1f} GN/m²
            - **Subgrade Modulus ($n_h$):** {options.nh} MN/m³ (user-defined)
            - **Moment of Inertia ($I$):** {I_m4:.4f} m⁴
            - **Flexural Rigidity ($EI$):** {EI_val:.1f} kN.m²
            
            **Methods:**
            - **Simplified (Reese-Matlock):** Analytical coefficients for linearly increasing soil modulus.
            - **Numerical (Finite Difference):** Includes **P-Δ effect** and improved soil stiffness model.
            """)
        g_rep1, g_rep2, g_rep3 = st.columns(3)
        with g_rep1:
            fig_m_rep = px.line(x=m_graph, y=z_graph, title="Moment (kNm)")
            fig_m_rep.update_yaxes(autorange="reversed"); st.plotly_chart(fig_m_rep, use_container_width=True, key="graph_moment_report")
        with g_rep2:
            fig_v_rep = px.line(x=v_graph, y=z_graph, title="Shear (kN)")
            fig_v_rep.update_yaxes(autorange="reversed"); st.plotly_chart(fig_v_rep, use_container_width=True, key="graph_shear_report")
        with g_rep3:
            fig_y_rep = px.line(x=y_graph, y=z_graph, title="Displacement (mm)")
            fig_y_rep.update_yaxes(autorange="reversed"); st.plotly_chart(fig_y_rep, use_container_width=True, key="graph_disp_report")
        
        with st.expander("📊 Detailed Lateral Analysis Table", expanded=False):
            lat_df = pd.DataFrame({
                "Depth (m)": z_graph,
                "Moment (kNm)": m_graph,
                "Shear (kN)": v_graph,
                "Disp (mm)": y_graph
            })
            if len(lat_df) > 30:
                lat_df_sampled = lat_df.iloc[::10].copy()
                lat_df_sampled = pd.concat([lat_df_sampled, lat_df.tail(1)]).drop_duplicates()
            else:
                lat_df_sampled = lat_df
                
            lat_html = f"<div style='margin-bottom:10px;'><b>{label_stiff} = {T_val:.3f} m</b></div>"
            lat_html += "<table class='print-table'><tr><th>Depth (m)</th><th>Moment (kNm)</th><th>Shear (kN)</th><th>Disp (mm)</th></tr>"
            for _, r in lat_df_sampled.iterrows():
                lat_html += f"<tr><td>{r['Depth (m)']:.2f}</td><td>{r['Moment (kNm)']:.2f}</td><td>{r['Shear (kN)']:.2f}</td><td>{r['Disp (mm)']:.2f}</td></tr>"
            lat_html += "</table>"
            st.markdown(lat_html, unsafe_allow_html=True)

        st.subheader("3. STRUCTURAL VERIFICATION")
        with st.expander("📝 Detailed Structural Calculations", expanded=True):
            st.markdown("**A. Axial Stress Check (Working):**")
            st.write(f"- Concrete Area (Ac) = {Ac:.0f} mm²")
            st.write(f"- Working Stress (fc) = Pw / Ac = {p_vertical*1000:.0f} / {Ac:.0f} = **{fc:.2f} MPa**")
            st.write(f"- Allowable Stress (fa) = 0.25 * fcu = 0.25 * {fcu} = **{fa:.2f} MPa**")
            
            st.markdown("**B. Capacity (Ultimate):**")
            st.write(f"- Steel Area (Asc) = {Asc:.0f} mm² ({bar_num} T{bar_dia})")
            st.write(f"- N_ult = (0.4*fcu*Ac + 0.75*fy*Asc) / 1000 = **{N_ult:.1f} kN**")
            
            st.markdown("**C. Reinforcement Requirement Analysis:**")
            st.write(f"- Absolute Code Minimum Ratio (ρ_min) = **0.40%**")
            
            as_m_req = (abs(Mmax) * 10**6) / (0.87 * fy * 0.7 * dia) if dia > 0 else 0
            as_n_req = ((p_vertical * 1000) - (0.4 * fcu * Ac)) / (0.75 * fy) if fy > 0 else 0
            
            st.latex(r"As_{moment} = \frac{M_{max}}{0.87 \cdot f_y \cdot 0.7 \cdot h} = " + f"{max(as_m_req, 0):.0f} " + r"mm^2")
            st.latex(r"As_{axial} = \frac{N - 0.4 \cdot f_{cu} \cdot A_c}{0.75 \cdot f_y} = " + f"{max(as_n_req, 0):.0f} " + r"mm^2")
            
            st.write(f"- Total Required Area (As_req) = max(0.004*Ac, As_m + As_n) = **{max(Ac * 0.004, as_m_req + as_n_req):.0f} mm²**")
            st.write(f"- Required Ratio (ρ_req) = **{rho_req:.2f}%** | Provided Ratio (ρ_prov) = **{rho_prov:.2f}%**")
            
            st.markdown("**D. Shear & Cracking:**")
            applied_shear = p_horizontal if p_horizontal > 0 else (0.03 * p_vertical if p_vertical > 0 else 0)
            v_app, v_lim, shear_ok = shear_check(Ac, applied_shear, fcu, rho_prov)
            st.write(f"- Applied Shear Force (V) = {applied_shear:.1f} kN")
            st.write(f"- Shear Stress (v) = V / Ac = **{v_app:.2f} MPa** vs Limit **{v_lim:.2f} MPa**")

        s_act, s_lim, s_ok = stirrup_spacing_check(dia, bar_dia, stirrup_sp)
        with st.expander("🔍 Detailed Stirrup Spacing Check", expanded=True):
            st.write(f"Limit = min(12×{bar_dia}, {dia}, 300) = **{s_lim} mm** | Actual = **{s_act} mm**")
            if s_ok: st.success("PASS")
            else: st.error("FAIL")

        st.subheader("4. CONCLUSION & VERIFICATION")
        summary_final = [
            {"Check": "Geotech FoS", "Req": f"> {options.fos_geotech}", "Act": f"{geo_res.get('FoS', 0):.2f}", "Status": "✅ PASS" if geo_res.get('FoS', 0) >= options.fos_geotech else "❌ FAIL"},
            {"Check": "Reinforcement %", "Req": f"min {rho_req}%", "Act": f"{rho_prov:.2f}%", "Status": "✅ PASS" if rho_ok else "❌ FAIL"},
            {"Check": "Stirrup Spacing", "Req": f"< {s_lim} mm", "Act": f"{s_act} mm", "Status": "✅ PASS" if s_ok else "❌ FAIL"},
            {"Check": "Shear Stress", "Req": f"< {v_lim:.2f} MPa", "Act": f"{v_app:.2f} MPa", "Status": "✅ PASS" if shear_ok else "❌ FAIL"},
            {"Check": "Max Displacement", "Req": f"< {allowable_deflection} mm", "Act": f"{max(y_graph):.2f} mm", "Status": "✅ PASS" if max(y_graph) <= allowable_deflection else "❌ FAIL"}
        ]
        st.table(pd.DataFrame(summary_final))

    st.markdown("""
        <style>
        @media print {
            [data-testid="stSidebar"], header, [data-testid="stHeader"], [data-baseweb="tab-list"], .stButton { display: none !important; }
            .main .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
            .main { background-color: white !important; }
            .js-plotly-plot { max-width: 100% !important; height: 350px !important; }
            .stTable { font-size: 9pt !important; }
            tr { page-break-inside: avoid; }
            h1, h2, h3 { color: black !important; }
        }
        </style>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.caption("v2.3.1 - P-Delta + Ks Fix + nh Control + Settlement")
