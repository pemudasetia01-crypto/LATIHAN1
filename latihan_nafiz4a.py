import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import st_folium
import numpy as np
import io

# Konfigurasi Halaman
st.set_page_config(page_title="WebGIS Data Ukur Malaysia", layout="wide")

st.title("🗺️ WebGIS Visualisasi & Analisis Poligon (Surveyor Edition)")

# --- SIDEBAR: KONTROL ---
st.sidebar.header("⚙️ Konfigurasi & Layer")
epsg_input = st.sidebar.text_input("Sistem Koordinat (EPSG)", value="3375") # Default: GDM2000 / Peninsular RSO
show_satelite = st.sidebar.checkbox("Tampilkan Citra Satelit", value=True)
show_labels = st.sidebar.checkbox("Tampilkan Label Stesen", value=True)
show_bearing_dist = st.sidebar.checkbox("Tampilkan Bearing & Jarak", value=True)

# --- FUNGSI PERHITUNGAN ---
def calculate_bearing_distance(df):
    dist_list = []
    bearing_list = []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        dist = np.sqrt(dx**2 + dy**2)
        angle = np.degrees(np.arctan2(dx, dy))
        bearing = (angle + 360) % 360
        
        dist_list.append(round(dist, 3))
        bearing_list.append(round(bearing, 2))
    return dist_list, bearing_list

# --- 1. UPLOAD FILE ---
uploaded_file = st.file_uploader("Muat naik CSV (Kolom: E, N, STN)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    if 'E' in df.columns and 'N' in df.columns:
        # Hitung Data Ukur
        distances, bearings = calculate_bearing_distance(df)
        df['Jarak'] = distances
        df['Bearing'] = bearings
        
        # Buat GeoDataFrame (Asal: RSO/UTM)
        coords = list(zip(df['E'], df['N']))
        poly_geom = Polygon(coords)
        gdf_original = gpd.GeoDataFrame(index=[0], crs=f"EPSG:{epsg_input}", geometry=[poly_geom])
        
        # Reproject ke WGS84 untuk Folium (Penting!)
        gdf_wgs84 = gdf_original.to_crs(epsg=4326)
        poly_wgs84 = gdf_wgs84.geometry.iloc[0]
        
        # Koordinat untuk Folium (Lat, Lon)
        lat_lon_coords = [[p[1], p[0]] for p in poly_wgs84.exterior.coords][:-1]

        # --- UI: RINGKASAN ---
        luas_m2 = poly_geom.area
        total_dist = sum(distances)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Luas (m²)", f"{luas_m2:.3f}")
        c2.metric("Keliling (m)", f"{total_dist:.3f}")
        c3.metric("Bilangan Stesen", len(df))

        # --- 3 & 4. WEBGIS DENGAN FOLIUM ---
        tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" if show_satelite else "OpenStreetMap"
        attr = "Google Satellite" if show_satelite else "OpenStreetMap"

        center = [poly_wgs84.centroid.y, poly_wgs84.centroid.x]
        m = folium.Map(location=center, zoom_start=19, tiles=tiles, attr=attr)

        # Lukis Polygon
        folium.Polygon(
            locations=lat_lon_coords,
            color="yellow", weight=3, fill=True, fill_opacity=0.3,
            tooltip=f"Luas: {luas_m2:.2f} m²"
        ).add_to(m)

        # Loop untuk Label & Bearing
        for i, row in df.iterrows():
            # Get WGS84 point for markers
            p_wgs = gdf_wgs84.geometry.iloc[0].exterior.coords[i]
            p_next_wgs = gdf_wgs84.geometry.iloc[0].exterior.coords[(i+1)%len(df)]
            
            if show_labels:
                folium.Marker(
                    location=[p_wgs[1], p_wgs[0]],
                    icon=folium.DivIcon(html=f'<div style="font-size: 10pt; color: yellow; text-shadow: 1px 1px black;"><b>{row["STN"]}</b></div>')
                ).add_to(m)
            
            if show_bearing_dist:
                mid_lat = (p_wgs[1] + p_next_wgs[1]) / 2
                mid_lon = (p_wgs[0] + p_next_wgs[0]) / 2
                folium.Marker(
                    location=[mid_lat, mid_lon],
                    icon=folium.DivIcon(html=f'<div style="font-size: 7pt; color: #00FFFF; white-space: nowrap;">{row["Bearing"]}° | {row["Jarak"]}m</div>')
                ).add_to(m)

        st_folium(m, width="100%", height=600)

        # --- 2. EXPORT DATA ---
        st.subheader("📥 Muat Turun Data")
        ex1, ex2, ex3 = st.columns(3)
        
        # GeoJSON
        geojson = gdf_original.to_json()
        ex1.download_button("Download GeoJSON", data=geojson, file_name="lot_ukur.geojson", mime="application/json")
        
        # CSV Lengkap
        csv_data = df.to_csv(index=False).encode('utf-8')
        ex2.download_button("Download CSV Lengkap", data=csv_data, file_name="data_stesen.csv", mime="text/csv")
        
        # Shapefile (Memerlukan folder zip)
        # Note: Shapefile memerlukan library tambahan, GeoJSON lebih praktikal untuk Web.
        
    else:
        st.error("Pastikan CSV mempunyai kolom 'E', 'N', dan 'STN'!")
