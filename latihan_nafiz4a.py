import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from folium.plugins import MeasureControl, MousePosition, Fullscreen
from streamlit_folium import st_folium
import numpy as np

# --- 1. PENGURUSAN LOGIN ---
ALLOWED_IDS = ["MUHAMMAD", "NAFIZ", "NAJMI"]

if 'password_db' not in st.session_state:
    st.session_state['password_db'] = 'admin123'
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_page():
    st.title("🔐 Sistem Surveyor WebGIS")
    user_id = st.selectbox("Pilih ID Pengguna", ALLOWED_IDS)
    pwd = st.text_input("Kata Laluan", type="password")
    if st.button("Login"):
        if pwd == st.session_state['password_db']:
            st.session_state['logged_in'] = True
            st.session_state['current_user'] = user_id
            st.rerun()
        else:
            st.error("Kata laluan salah!")

# --- 2. FUNGSI GEOMETRI ---
def decimal_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m/60) * 3600, 1)
    return f"{d}°{abs(m)}'{abs(s)}\""

def calculate_survey_labels(df, poly_meter, offset_dist):
    results = []
    centroid = poly_meter.centroid
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        mid_e, mid_n = (p1['E'] + p2['E']) / 2, (p1['N'] + p2['N']) / 2
        dx, dy = p2['E'] - p1['E'], p2['N'] - p1['N']
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing = decimal_to_dms((np.degrees(angle_rad) + 360) % 360)
        rotation = np.degrees(angle_rad) - 90
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
        
        v_e, v_n = mid_e - centroid.x, mid_n - centroid.y
        v_mag = np.sqrt(v_e**2 + v_n**2)
        off_e = mid_e + (v_e / v_mag * offset_dist)
        off_n = mid_n + (v_n / v_mag * offset_dist)
        
        results.append({
            'dari_stn': p1['STN'],
            'ke_stn': p2['STN'],
            'bearing': bearing, 
            'distance': f"{dist:.3f}m", 
            'rotation': rotation, 
            'off_e': off_e, 
            'off_n': off_n
        })
    return results

# --- 3. MAIN APP ---
if not st.session_state['logged_in']:
    login_page()
else:
    st.set_page_config(page_title="Surveyor Pro WebGIS", layout="wide")
    
    st.title("🛰️ Johor Grid WebGIS (EPSG:4390)")

    with st.sidebar:
        st.markdown(f"### 👋 Hi, **{st.session_state['current_user']}**")
        if st.button("Log Keluar"):
            st.session_state['logged_in'] = False
            st.rerun()

        st.header("⚙️ Tetapan Visual")
        show_labels = st.checkbox("Bearing & Jarak di Peta", value=True)
        text_size = st.slider("Saiz Teks Label", 6, 20, 10)
        offset_val = st.slider("Jarak Label (m)", 0.1, 10.0, 1.8)
        
        st.header("📂 Data")
        uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        area = poly_meter.area
        perimeter = poly_meter.length
        label_data = calculate_survey_labels(df, poly_meter, offset_val)

        # PAPARAN PETA
        gdf_poly = gpd.GeoDataFrame(index=[0], crs="EPSG:4390", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_poly.geometry.iloc[0]
        
        m = folium.Map(location=[poly_wgs.centroid.y, poly_wgs.centroid.x], zoom_start=19)
        folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Satellite").add_to(m)
        folium.Polygon(locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords], color="#00FFFF", weight=2, fill=True, fill_opacity=0.1).add_to(m)

        if show_labels:
            off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
            gdf_off_wgs = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:4390").to_crs(epsg=4326)
            for i, data in enumerate(label_data):
                pos_wgs = gdf_off_wgs.iloc[i].geometry
                label_html = f'<div style="transform: translate(-50%, -50%) rotate({data["rotation"]}deg); color: yellow; font-weight: bold; text-shadow: 2px 2px black; font-size: {text_size}pt;">{data["bearing"]}<br>{data["distance"]}</div>'
                folium.Marker([pos_wgs.y, pos_wgs.x], icon=folium.DivIcon(html=label_html)).add_to(m)

        st_folium(m, use_container_width=True, height=500)

        # --- PENAMBAHAN JADUAL DI BAWAH PETA ---
        st.markdown("---")
        st.subheader("📋 Ringkasan Maklumat Lot")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Keluasan (Area)", f"{area:.3f} m²")
        col2.metric("Perimeter", f"{perimeter:.3f} m")
        col3.metric("Bilangan Stesen", len(df))

        st.subheader("📑 Jadual Data Survey (Bearing & Jarak)")
        
        # Sediakan data untuk jadual
        table_data = []
        for item in label_data:
            table_data.append({
                "Dari STN": item['dari_stn'],
                "Ke STN": item['ke_stn'],
                "Bearing": item['bearing'],
                "Jarak (m)": item['distance']
            })
        
        df_table = pd.DataFrame(table_data)
        st.dataframe(df_table, use_container_width=True)

        st.subheader("📍 Koordinat Stesen (Johor Grid)")
        st.dataframe(df[['STN', 'E', 'N']].set_index('STN'), use_container_width=True)

    else:
        st.info("Sila muat naik fail CSV untuk melihat peta dan jadual.")
