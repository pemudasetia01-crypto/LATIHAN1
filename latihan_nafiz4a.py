import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, mapping
import folium
from folium.plugins import MeasureControl, MousePosition, Fullscreen
from streamlit_folium import st_folium
import numpy as np
import json

# --- 1. PENGURUSAN PASSWORD & SESSION ---
if 'password' not in st.session_state:
    st.session_state['password'] = 'admin123'
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_page():
    st.title("🔐 Login Sistem Surveyor")
    name = st.text_input("Nama Pengguna (ID 1)")
    pwd = st.text_input("Kata Laluan", type="password")
    
    col1, col2 = st.columns(2)
    if col1.button("Login"):
        if pwd == st.session_state['password']:
            st.session_state['logged_in'] = True
            st.session_state['user_name'] = name
            st.rerun()
        else:
            st.error("Kata laluan salah!")
            
    if col2.button("Lupa Password?"):
        st.session_state['reset_mode'] = True

    if st.session_state.get('reset_mode'):
        new_pwd = st.text_input("Masukkan Password Baru")
        if st.button("Simpan Password Baru"):
            st.session_state['password'] = new_pwd
            st.session_state['reset_mode'] = False
            st.success("Password baru telah disimpan! Sila login.")

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
        p1, p2 = df.iloc[i], df.iloc[(i + 1) % len(df)]
        dx, dy = p2['E'] - p1['E'], p2['N'] - p1['N']
        mid_e, mid_n = (p1['E'] + p2['E']) / 2, (p1['N'] + p2['N']) / 2
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing = decimal_to_dms((np.degrees(angle_rad) + 360) % 360)
        
        rotation = np.degrees(angle_rad) - 90
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
        
        # Offset calculation
        mag = np.sqrt((mid_e - centroid.x)**2 + (mid_n - centroid.y)**2)
        off_e = mid_e + ((mid_e - centroid.x) / mag * offset_dist)
        off_n = mid_n + ((mid_n - centroid.y) / mag * offset_dist)
        
        results.append({'bearing': bearing, 'distance': f"{dist:.3f}m", 'rotation': rotation, 'off_e': off_e, 'off_n': off_n})
    return results

# --- MAIN APP ---
if not st.session_state['logged_in']:
    login_page()
else:
    st.set_page_config(page_title="Surveyor Pro WebGIS", layout="wide")
    st.sidebar.write(f"👋 Hi, **{st.session_state['user_name']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    st.title("🛰️ Johor Grid WebGIS (EPSG:4390)")

    # Sidebar Kawalan
    with st.sidebar:
        st.header("⚙️ Tetapan Paparan")
        text_size = st.slider("Saiz Teks Label", 5, 20, 10)
        marker_size = st.slider("Saiz Titik Stesen", 2, 10, 5)
        offset_val = st.slider("Jarak Label (Meter)", 1.0, 10.0, 3.0)
        
        st.header("📂 Data")
        uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        
        # Geoprocessing
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        label_data = calculate_survey_labels(df, poly_meter, offset_val)
        
        # Convert to WGS84
        gdf_poly = gpd.GeoDataFrame(index=[0], crs="EPSG:4390", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_poly.geometry.iloc[0]
        
        off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
        gdf_off_wgs = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:4390").to_crs(epsg=4326)

        # Info Ringkas
        perimeter = poly_meter.length
        area_m2 = poly_meter.area
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Luas", f"{area_m2:.3f} m²")
        col2.metric("Perimeter", f"{perimeter:.3f} m")
        
        # --- EXPORT QGIS (GeoJSON) ---
        geojson_data = gdf_poly.to_json()
        st.download_button(
            label="📥 Export ke QGIS (GeoJSON)",
            data=geojson_data,
            file_name="lot_survey.geojson",
            mime="application/json"
        )

        # --- MAP ---
        m = folium.Map(location=[poly_wgs.centroid.y, poly_wgs.centroid.x], zoom_start=19, max_zoom=22)
        
        folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", 
                         attr="Google", name="Google Hybrid", max_zoom=22, max_native_zoom=20).add_to(m)

        # Polygon Layer dengan Popup Maklumat
        folium.Polygon(
            locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords],
            color="cyan", weight=3, fill=True, fill_opacity=0.2,
            tooltip="Klik untuk info lot",
            popup=f"<b>MAKLUMAT LOT</b><br>Luas: {area_m2:.3f} m²<br>Perimeter: {perimeter:.3f} m"
        ).add_to(m)

        # Stesen & Label
        for i, row in df.iterrows():
            stn_wgs = poly_wgs.exterior.coords[i]
            # Point Stesen keluar koordinat
            folium.CircleMarker(
                [stn_wgs[1], stn_wgs[0]], radius=marker_size, color="red", fill=True,
                popup=f"<b>STN: {row['STN']}</b><br>E: {row['E']}<br>N: {row['N']}<br>Lat: {stn_wgs[1]:.6f}<br>Lon: {stn_wgs[0]:.6f}"
            ).add_to(m)

            # Label Bearing & Jarak
            data = label_data[i]
            pos_wgs = gdf_off_wgs.iloc[i].geometry
            label_html = f"""<div style="transform: translate(-50%,-50%) rotate({data['rotation']}deg); text-align: center; pointer-events: none;">
                             <div style="font-size: {text_size}pt; color: #00FF00; font-weight: bold; text-shadow: 2px 2px 2px #000;">{data['bearing']}<br>{data['distance']}</div>
                             </div>"""
            folium.Marker([pos_wgs.y, pos_wgs.x], icon=folium.DivIcon(html=label_html)).add_to(m)

        # Plugins
        Fullscreen().add_to(m)
        MeasureControl(primary_length_unit='meters').add_to(m)
        MousePosition().add_to(m)
        
        st_folium(m, use_container_width=True, height=700)
