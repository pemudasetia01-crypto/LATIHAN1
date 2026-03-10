import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import st_folium
import numpy as np

# --- 1. FUNGSI TUKAR PERPULUHAN KE DMS ---
def decimal_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m/60) * 3600, 1)
    if s >= 60:
        m += 1
        s = 0
    return f"{d}°{abs(m)}'{abs(s)}\""

# --- 2. FUNGSI KIRA DATA UKUR & ROTASI TEKS ---
def calculate_survey_data(df):
    dist_list, bearing_dms_list, text_angles = [], [], []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        # Jarak
        dist = np.sqrt(dx**2 + dy**2)
        
        # Bearing (Azimuth dari Utara)
        angle_rad = np.arctan2(dx, dy)
        bearing_deg = (np.degrees(angle_rad) + 360) % 360
        
        # Logik Rotasi Teks: 
        # Sudut CSS bermula dari Timur (90 deg perbezaan dengan Utara)
        # Kita tolak 90 supaya 0° (Utara) menjadi tegak.
        rotation = np.degrees(angle_rad) - 90
        
        # Pastikan teks sentiasa boleh dibaca (tidak terbalik 180 darjah)
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180

        dist_list.append(round(dist, 3))
        bearing_dms_list.append(decimal_to_dms(bearing_deg))
        text_angles.append(rotation)
        
    return dist_list, bearing_dms_list, text_angles

# --- 3. UI STREAMLIT ---
st.set_page_config(page_title="WebGIS Surveyor Pro", layout="wide")
st.title("📐 WebGIS: Label Selari & Ikut Bearing")

uploaded_file = st.file_uploader("Muat naik fail CSV (Format: STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if all(col in df.columns for col in ['E', 'N', 'STN']):
        
        distances, bearings, rotations = calculate_survey_data(df)
        df['Jarak'] = distances
        df['Bearing'] = bearings
        df['Rotation'] = rotations

        # Proses Koordinat (RSO ke WGS84)
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        gdf_wgs = gpd.GeoDataFrame(index=[0], crs="EPSG:3375", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_wgs.geometry.iloc[0]
        centroid = poly_wgs.centroid

        # Paparan Ringkasan
        st.columns(3)[0].metric("Luas", f"{poly_meter.area:.3f} m²")
        st.columns(3)[1].metric("Keliling", f"{sum(distances):.3f} m")

        # Konfigurasi Peta
        m = folium.Map(
            location=[centroid.y, centroid.x],
            zoom_start=20,
            max_zoom=22
        )
        
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            name="Google Satellite",
            max_zoom=22,
            max_native_zoom=20,
            attr="Google Maps"
        ).add_to(m)

        # Lukis Garisan Poligon
        folium.Polygon(
            locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords],
            color="cyan", weight=3, fill=True, fill_opacity=0.1
        ).add_to(m)

        # Tambah Label Bersebelahan & Rotate
        for i, row in df.iterrows():
            p_curr = poly_wgs.exterior.coords[i]
            p_next = poly_wgs.exterior.coords[(i+1)%len(df)]
            
            # Label Stesen
            folium.Marker(
                [p_curr[1], p_curr[0]],
                icon=folium.DivIcon(html=f'<div style="color:white; background:red; border-radius:50%; width:10px; height:10px; border:1px solid white;"></div>')
            ).add_to(m)

            # Titik Tengah Garisan
            mid_lat = (p_curr[1] + p_next[1]) / 2
            mid_lon = (p_curr[0] + p_next[0]) / 2
            
            # Offset ke luar lot supaya tidak tindih garisan
            off_lat = mid_lat + (mid_lat - centroid.y) * 0.1
            off_lon = mid_lon + (mid_lon - centroid.x) * 0.1

            # HTML & CSS untuk pusingkan teks ikut bearing
            label_html = f"""
                <div style="
                    transform: rotate({row['Rotation']}deg); 
                    transform-origin: center;
                    white-space: nowrap; 
                    display: inline-block;
                ">
                    <div style="
                        font-size: 9pt; 
                        color: #FFFF00; 
                        font-weight: bold; 
                        text-shadow: 1px 1px 2px black;
                        margin-bottom: -3px;
                    ">
                        {row['Bearing']}
                    </div>
                    <div style="
                        font-size: 8pt; 
                        color: #00FF00; 
                        font-weight: bold; 
                        text-shadow: 1px 1px 2px black;
                    ">
                        {row['Jarak']}m
                    </div>
                </div>"""
            
            folium.Marker(
                [off_lat, off_lon], 
                icon=folium.DivIcon(html=label_html)
            ).add_to(m)

        st_folium(m, use_container_width=True, height=700)
    else:
        st.error("Pastikan CSV ada kolum STN, E, dan N.")
