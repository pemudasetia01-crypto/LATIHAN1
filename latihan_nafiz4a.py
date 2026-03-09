import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import st_folium
import numpy as np

# Konfigurasi Halaman
st.set_page_config(page_title="WebGIS Data Ukur", layout="wide")

st.title("🗺️ WebGIS Visualisasi & Analisis Poligon")

# --- SIDEBAR: KONTROL ---
st.sidebar.header("Konfigurasi & Layer")
show_satelite = st.sidebar.checkbox("Tampilkan Citra Satelit", value=True)
show_labels = st.sidebar.checkbox("Tampilkan Label Stasiun", value=True)
show_bearing_dist = st.sidebar.checkbox("Tampilkan Bearing & Jarak", value=False)

# --- FUNGSI PERHITUNGAN ---
def calculate_bearing_distance(df):
    # Menghitung jarak dan bearing antar titik
    dist_list = []
    bearing_list = []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)] # Titik selanjutnya (looping ke awal)
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        dist = np.sqrt(dx**2 + dy**2)
        # Hitung azimuth (bearing)
        angle = np.degrees(np.arctan2(dx, dy))
        bearing = (angle + 360) % 360
        
        dist_list.append(round(dist, 2))
        bearing_list.append(round(bearing, 2))
    return dist_list, bearing_list

# --- 1. UPLOAD FILE ---
uploaded_file = st.file_uploader("Unggah file CSV (Minimal kolom: E, N, STN)", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    if 'E' in df.columns and 'N' in df.columns:
        # Hitung Data Tambahan
        distances, bearings = calculate_bearing_distance(df)
        
        # Buat Geometri Polygon
        coords = list(zip(df['E'], df['N']))
        poly_geom = Polygon(coords)
        gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:32748", geometry=[poly_geom]) # Sesuaikan kode EPSG daerah Anda
        
        # Hitung Luas
        luas_m2 = poly_geom.area
        
        # --- UI: INFORMASI ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Luas Area", f"{luas_m2:.2f} m²")
        col2.metric("Jumlah Titik", len(df))
        col3.metric("Keliling", f"{sum(distances):.2f} m")

        # --- 3 & 4. WEBGIS DENGAN FOLIUM ---
        # Tentukan basemap
        tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" if show_satelite else "OpenStreetMap"
        attr = "Google Satellite" if show_satelite else "OpenStreetMap"

        m = folium.Map(location=[df['N'].mean(), df['E'].mean()], zoom_start=18, tiles=tiles, attr=attr)

        # Tambahkan Polygon ke Peta
        # Catatan: Folium menggunakan (Lat, Lon). Jika E/N adalah UTM, perlu konversi ke Lat/Lon.
        # Asumsi di bawah ini: data sudah dalam koordinat geografis atau diproses sebagai bentuk relatif.
        points = [[row['N'], row['E']] for _, row in df.iterrows()]
        folium.Polygon(locations=points, color="yellow", weight=3, fill=True, fill_opacity=0.2).add_to(m)

        # Layer On/Off Label & Bearing
        for i, row in df.iterrows():
            if show_labels:
                folium.Marker(
                    location=[row['N'], row['E']],
                    icon=folium.DivIcon(html=f'<div style="font-size: 12pt; color: white; font-weight: bold;">{int(row["STN"])}</div>')
                ).add_to(m)
            
            if show_bearing_dist:
                mid_n = (row['N'] + points[(i+1)%len(points)][0]) / 2
                mid_e = (row['E'] + points[(i+1)%len(points)][1]) / 2
                folium.Marker(
                    location=[mid_n, mid_e],
                    icon=folium.DivIcon(html=f'<div style="font-size: 8pt; color: cyan;">{bearings[i]}° | {distances[i]}m</div>')
                ).add_to(m)

        # Tampilkan Peta
        st_folium(m, width=900, height=500)

        # --- 2. EXPORT DATA ---
        st.subheader("📥 Export Data")
        col_ex1, col_ex2 = st.columns(2)
        
        # Export GeoJSON
        geojson_data = gdf.to_json()
        col_ex1.download_button("Download GeoJSON", data=geojson_data, file_name="data_ukur.geojson", mime="application/json")
        
        # Export CSV hasil perhitungan
        df['Jarak_ke_Next'] = distances
        df['Bearing_ke_Next'] = bearings
        csv = df.to_csv(index=False).encode('utf-8')
        col_ex2.download_button("Download CSV (dengan Bearing/Jarak)", data=csv, file_name="data_ukur_Lengkap.csv", mime="text/csv")

    else:
        st.error("Kolom 'E' dan 'N' tidak ditemukan!")
