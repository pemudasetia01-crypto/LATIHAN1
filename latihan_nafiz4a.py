import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import st_folium
import numpy as np

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="WebGIS Data Ukur Malaysia", layout="wide")

st.title("🗺️ WebGIS Visualisasi & Analisis Poligon (Surveyor Edition)")
st.markdown("Aplikasi ini menukar koordinat meter (RSO/UTM) ke WebGIS untuk paparan satelit.")

# --- SIDEBAR: KONTROL ---
st.sidebar.header("⚙️ Konfigurasi & Layer")
# EPSG 3375 adalah standard untuk GDM2000 Peninsular Malaysia RSO
epsg_input = st.sidebar.text_input("Sistem Koordinat (EPSG)", value="3375") 
show_satelite = st.sidebar.checkbox("Tampilkan Citra Satelit", value=True)
show_labels = st.sidebar.checkbox("Tampilkan Label Stesen", value=True)
show_bearing_dist = st.sidebar.checkbox("Tampilkan Bearing & Jarak", value=True)

# --- FUNGSI PERHITUNGAN ---
def calculate_bearing_distance(df):
    dist_list = []
    bearing_list = []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)] # Loop balik ke titik asal
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        dist = np.sqrt(dx**2 + dy**2)
        # Kira Azimuth
        angle = np.degrees(np.arctan2(dx, dy))
        bearing = (angle + 360) % 360
        
        dist_list.append(round(dist, 3))
        bearing_list.append(round(bearing, 2))
    return dist_list, bearing_list

# --- 1. UPLOAD FILE ---
uploaded_file = st.file_uploader("Muat naik fail CSV (Format: STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # Semak jika kolum wujud
    if 'E' in df.columns and 'N' in df.columns:
        # Hitung Data Ukur (Jarak & Bearing)
        distances, bearings = calculate_bearing_distance(df)
        df['Jarak_m'] = distances
        df['Bearing_deg'] = bearings
        
        # --- PROSES GEOSPASIAL ---
        # 1. Bina Poligon dalam sistem koordinat asal (Meter)
        coords = list(zip(df['E'], df['N']))
        poly_geom = Polygon(coords)
        gdf_original = gpd.GeoDataFrame(index=[0], crs=f"EPSG:{epsg_input}", geometry=[poly_geom])
        
        # 2. Tukar (Reproject) ke WGS84 untuk Folium (Lat/Lon)
        gdf_wgs84 = gdf_original.to_crs(epsg=4326)
        poly_wgs84 = gdf_wgs84.geometry.iloc[0]
        
        # 3. Dapatkan titik-titik dalam format [Lat, Lon]
        lat_lon_coords = [[p[1], p[0]] for p in poly_wgs84.exterior.coords][:-1]

        # --- TAMPILAN RINGKASAN (METRIC) ---
        luas_m2 = poly_geom.area
        total_dist = sum(distances)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Luas (m²)", f"{luas_m2:.3f}")
        col2.metric("Keliling (m)", f"{total_dist:.3f}")
        col3.metric("Bilangan Stesen", len(df))

        # --- 2. WEBGIS DENGAN FOLIUM ---
        # Pilih basemap
        if show_satelite:
            tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
            attr = "Google Satellite"
        else:
            tiles = "OpenStreetMap"
            attr = "OpenStreetMap"

        # PENTING: max_zoom ditetapkan ke 22 untuk membolehkan zum rapat
        center = [poly_wgs84.centroid.y, poly_wgs84.centroid.x]
        m = folium.Map(
            location=center, 
            zoom_start=19, 
            tiles=tiles, 
            attr=attr,
            max_zoom=22 
        )

        # Lukis Poligon Lot
        folium.Polygon(
            locations=lat_lon_coords,
            color="yellow",
            weight=3,
            fill=True,
            fill_opacity=0.3,
            tooltip=f"Luas: {luas_m2:.2f} m²"
        ).add_to(m)

        # Tambah Label Stesen & Bearing/Jarak
        for i, row in df.iterrows():
            # Koordinat WGS84 untuk Marker
            p_curr = gdf_wgs84.geometry.iloc[0].exterior.coords[i]
            p_next = gdf_wgs84.geometry.iloc[0].exterior.coords[(i+1)%len(df)]
            
            # Label Nama Stesen (STN)
            if show_labels:
                folium.Marker(
                    location=[p_curr[1], p_curr[0]],
                    icon=folium.DivIcon(
                        html=f"""<div style="font-size: 10pt; color: white; font-weight: bold; 
                              text-shadow: 2px 2px 4px #000000; width: 50px;">
                              {row['STN']}</div>"""
                    )
                ).add_to(m)
            
            # Label Bearing & Jarak (di tengah-tengah garisan)
            if show_bearing_dist:
                mid_lat = (p_curr[1] + p_next[1]) / 2
                mid_lon = (p_curr[0] + p_next[0]) / 2
                folium.Marker(
                    location=[mid_lat, mid_lon],
                    icon=folium.DivIcon(
                        html=f"""<div style="font-size: 8pt; color: #00FFFF; font-weight: bold;
                              text-shadow: 1px 1px 2px #000000; white-space: nowrap;">
                              {row['Bearing_deg']}° | {row['Jarak_m']}m</div>"""
                    )
                ).add_to(m)

        # Paparkan Peta ke Streamlit
        st_folium(m, use_container_width=True, height=600)

        # --- 3. EXPORT DATA ---
        st.subheader("📥 Muat Turun Data")
        ex1, ex2 = st.columns(2)
        
        # GeoJSON Export
        geojson_str = gdf_original.to_json()
        ex1.download_button(
            label="Download GeoJSON",
            data=geojson_str,
            file_name="lot_ukur.geojson",
            mime="application/json"
        )
        
        # CSV Export (Bersama hasil kiraan)
        csv_data = df.to_csv(index=False).encode('utf-8')
        ex2.download_button(
            label="Download CSV Lengkap",
            data=csv_data,
            file_name="data_stesen_lengkap.csv",
            mime="text/csv"
        )
        
    else:
        st.error("Ralat: Pastikan fail CSV anda mempunyai kolum 'E', 'N', dan 'STN'.")

else:
    st.info("Sila muat naik fail CSV koordinat untuk bermula.")
