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
st.markdown("Aplikasi ini menukar koordinat meter (RSO/UTM) ke WebGIS dengan format ukuran JUPEM.")

# --- FUNGSI PEMBANTU ---
def decimal_to_dms(deg):
    """Menukar decimal degree ke format D° M' S\""""
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m/60) * 3600, 1)
    # Pastikan saat tidak jadi 60
    if s >= 60:
        m += 1
        s = 0
    return f"{d}° {abs(m)}' {abs(s)}\""

def calculate_bearing_distance(df):
    dist_list = []
    bearing_dms_list = []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        dist = np.sqrt(dx**2 + dy**2)
        angle = np.degrees(np.arctan2(dx, dy))
        bearing_decimal = (angle + 360) % 360
        
        dist_list.append(round(dist, 3))
        bearing_dms_list.append(decimal_to_dms(bearing_decimal))
    return dist_list, bearing_dms_list

# --- SIDEBAR ---
st.sidebar.header("⚙️ Konfigurasi")
epsg_input = st.sidebar.text_input("Sistem Koordinat (EPSG)", value="3375") 
show_satelite = st.sidebar.checkbox("Tampilkan Citra Satelit", value=True)

# --- 1. UPLOAD FILE ---
uploaded_file = st.file_uploader("Muat naik fail CSV (Format: STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    if 'E' in df.columns and 'N' in df.columns:
        # Hitung Data Ukur
        distances, bearings_dms = calculate_bearing_distance(df)
        df['Jarak_m'] = distances
        df['Bearing_DMS'] = bearings_dms
        
        # Proses Geospasial
        coords = list(zip(df['E'], df['N']))
        poly_geom = Polygon(coords)
        gdf_original = gpd.GeoDataFrame(index=[0], crs=f"EPSG:{epsg_input}", geometry=[poly_geom])
        gdf_wgs84 = gdf_original.to_crs(epsg=4326)
        poly_wgs84 = gdf_wgs84.geometry.iloc[0]
        
        # --- RINGKASAN DATA ---
        luas_m2 = poly_geom.area
        # Tukar ke Hektar/Ekar jika perlu
        st.columns(3)[0].metric("Luas (m²)", f"{luas_m2:.3f}")
        st.columns(3)[1].metric("Keliling (m)", f"{sum(distances):.3f}")
        st.columns(3)[2].metric("Bilangan Stesen", len(df))

        # --- 2. MAP SETTINGS ---
        tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" if show_satelite else "OpenStreetMap"
        m = folium.Map(location=[poly_wgs84.centroid.y, poly_wgs84.centroid.x], 
                       zoom_start=19, tiles=tiles, attr="Google/OSM", max_zoom=22)

        # Lukis Poligon
        folium.Polygon(
            locations=[[p[1], p[0]] for p in poly_wgs84.exterior.coords],
            color="yellow", weight=3, fill=True, fill_opacity=0.2
        ).add_to(m)

        # Tambah Label (Stesen & Ukuran)
        centroid = poly_wgs84.centroid
        for i, row in df.iterrows():
            p_curr = poly_wgs84.exterior.coords[i]
            p_next = poly_wgs84.exterior.coords[(i+1)%len(df)]
            
            # --- OFFSET LOGIC (Supaya label di luar lot) ---
            # Cari arah dari centroid ke titik untuk 'tolak' label ke luar
            def get_offset_pos(point, ref_point, offset=0.00005):
                lat = point[1] + (point[1] - ref_point.y) * 1.2 # Faktor 1.2 untuk jarak luar
                lon = point[0] + (point[0] - ref_point.x) * 1.2
                return [lat, lon]

            # Label Nama Stesen (STN)
            stn_pos = [p_curr[1], p_curr[0]]
            folium.Marker(
                location=stn_pos,
                icon=folium.DivIcon(html=f"""<div style="font-size: 10pt; color: #FF00FF; font-weight: bold; 
                text-shadow: 1px 1px 2px black; width: 40px;">{row['STN']}</div>""")
            ).add_to(m)

            # Label Bearing & Jarak (Tengah Garisan & Di Luar)
            mid_p = [(p_curr[1] + p_next[1]) / 2, (p_curr[0] + p_next[0]) / 2]
            # Offset sedikit dari tengah ke arah luar
            off_lat = mid_p[0] + (mid_p[0] - centroid.y) * 0.2
            off_lon = mid_p[1] + (mid_p[1] - centroid.x) * 0.2

            folium.Marker(
                location=[off_lat, off_lon],
                icon=folium.DivIcon(html=f"""
                <div style="font-size: 8pt; color: #00FFFF; font-weight: bold; text-align: center;
                text-shadow: 1px 1px 2px black; line-height: 1.1; white-space: nowrap;">
                    {row['Bearing_DMS']}<br>
                    <span style="color: #00FF00;">{row['Jarak_m']}m</span>
                </div>""")
            ).add_to(m)

        st_folium(m, use_container_width=True, height=600)

        # --- 3. EXPORT ---
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV Lengkap (DMS)", csv_data, "data_ukur.csv", "text/csv")
    else:
        st.error("Format CSV salah!")
