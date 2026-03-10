import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import st_folium
import numpy as np

# --- FUNGSI TUKAR DMS (Darjah, Minit, Saat) ---
def decimal_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m/60) * 3600, 1)
    if s >= 60:
        m += 1
        s = 0
    return f"{d}°{abs(m)}'{abs(s)}\""

# --- FUNGSI KIRA DATA UKUR & SUDUT LABEL ---
def calculate_survey_data(df):
    dist_list, bearing_dms_list, text_angles = [], [], []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        # Jarak & Bearing
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing_deg = (np.degrees(angle_rad) + 360) % 360
        
        # Kira kecondongan teks (Rotation)
        # Kita sesuaikan supaya teks sentiasa "membaca" dari bawah ke atas/kiri ke kanan
        rotation = 90 - np.degrees(angle_rad)
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180

        dist_list.append(round(dist, 3))
        bearing_dms_list.append(decimal_to_dms(bearing_deg))
        text_angles.append(rotation)
        
    return dist_list, bearing_dms_list, text_angles

# --- KONFIGURASI STREAMLIT ---
st.set_page_config(page_title="WebGIS Surveyor Pro", layout="wide")
st.title("📐 WebGIS Poligon (Ultra Zoom Edition)")

uploaded_file = st.file_uploader("Muat naik fail CSV (Format: STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if all(col in df.columns for col in ['E', 'N', 'STN']):
        
        # Pengiraan Data
        distances, bearings, rotations = calculate_survey_data(df)
        df['Jarak'] = distances
        df['Bearing'] = bearings
        df['Rotation'] = rotations

        # Proses Geospasial (EPSG 3375 untuk Semenanjung)
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        gdf_wgs = gpd.GeoDataFrame(index=[0], crs="EPSG:3375", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_wgs.geometry.iloc[0]
        centroid = poly_wgs.centroid

        # Paparan Luas Automatik
        luas_m2 = poly_meter.area
        c1, c2, c3 = st.columns(3)
        c1.metric("Luas (m²)", f"{luas_m2:.3f}")
        c2.metric("Luas (Ekar)", f"{(luas_m2 * 0.0002471):.4f}")
        c3.info("Gunakan skrol tetikus untuk zum rapat (Max: 22)")

        # --- KONFIGURASI PETA (ZOOM MAKSIMUM) ---
        # Menggunakan Google Satellite untuk sokongan zum tinggi
        google_sat = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        
        m = folium.Map(
            location=[centroid.y, centroid.x],
            zoom_start=19,
            max_zoom=22,  # Membolehkan zum sehingga level 22
            tiles=None    # Kita set tiles secara manual di bawah
        )
        
        folium.TileLayer(
            tiles=google_sat,
            name="Google Satellite",
            max_zoom=22,         # PENTING: Mesti set di sini juga
            max_native_zoom=20,  # Google biasanya native sampai 20, selebihnya dia akan 'stretch' (upscale)
            attr="Google Maps"
        ).add_to(m)

        # Lukis Lot
        folium.Polygon(
            locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords],
            color="#00FFFF", weight=2, fill=True, fill_opacity=0.15
        ).add_to(m)

        # Tambah Label (Stesen & Ukuran Selari)
        for i, row in df.iterrows():
            p_curr = poly_wgs.exterior.coords[i]
            p_next = poly_wgs.exterior.coords[(i+1)%len(df)]
            
            # Label Stesen
            folium.Marker(
                [p_curr[1], p_curr[0]],
                icon=folium.DivIcon(html=f'<div style="color:#FF00FF; font-weight:bold; font-size:10pt; text-shadow: 1px 1px black;">{row["STN"]}</div>')
            ).add_to(m)

            # Titik tengah garisan untuk Label Ukuran
            mid_lat = (p_curr[1] + p_next[1]) / 2
            mid_lon = (p_curr[0] + p_next[0]) / 2
            
            # Tolak label ke luar sedikit (Offset)
            off_lat = mid_lat + (mid_lat - centroid.y) * 0.2
            off_lon = mid_lon + (mid_lon - centroid.x) * 0.2

            # HTML dengan CSS Rotation
            label_html = f"""
                <div style="
                    transform: rotate({row['Rotation']}deg); 
                    white-space: nowrap; 
                    text-align: center;
                    pointer-events: none;
                ">
                    <div style="font-size: 8pt; color: #FFFF00; font-weight: bold; text-shadow: 1px 1px 2px black;">{row['Bearing']}</div>
                    <div style="font-size: 8pt; color: #FFFFFF; font-weight: bold; text-shadow: 1px 1px 2px black;">{row['Jarak']}m</div>
                </div>"""
            
            folium.Marker([off_lat, off_lon], icon=folium.DivIcon(html=label_html)).add_to(m)

        # Paparkan Peta
        st_folium(m, use_container_width=True, height=700)
    else:
        st.error("Format CSV tidak sah. Pastikan ada kolum STN, E, N.")
