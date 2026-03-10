import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from streamlit_folium import st_folium
import numpy as np

# --- FUNGSI TUKAR DMS ---
def decimal_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m/60) * 3600, 1)
    if s >= 60:
        m += 1
        s = 0
    return f"{d}°{abs(m)}'{abs(s)}\""

# --- FUNGSI KIRA BEARING & JARAK ---
def calculate_survey_data(df):
    dist_list, bearing_dms_list, angles = [], [], []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing_deg = (np.degrees(angle_rad) + 360) % 360
        
        # Sudut untuk pusingan teks (Folium menggunakan sistem darjah kartesian)
        # Kita tolak 90 darjah supaya teks mendatar selari dengan garisan
        text_angle = 90 - np.degrees(angle_rad)
        if text_angle > 90: text_angle -= 180
        if text_angle < -90: text_angle += 180

        dist_list.append(round(dist, 3))
        bearing_dms_list.append(decimal_to_dms(bearing_deg))
        angles.append(text_angle)
        
    return dist_list, bearing_dms_list, angles

# --- UI STREAMLIT ---
st.set_page_config(page_title="WebGIS Surveyor Pro", layout="wide")
st.title("📐 WebGIS Poligon: Label Selari & Luas Automatik")

uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if all(x in df.columns for x in ['E', 'N', 'STN']):
        distances, bearings, text_rotations = calculate_survey_data(df)
        df['Jarak'] = distances
        df['Bearing'] = bearings
        df['Rotation'] = text_rotations

        # Geoprocessing
        poly_original = Polygon(list(zip(df['E'], df['N'])))
        gdf_wgs84 = gpd.GeoDataFrame(index=[0], crs="EPSG:3375", geometry=[poly_original]).to_crs(epsg=4326)
        poly_wgs = gdf_wgs84.geometry.iloc[0]
        centroid = poly_wgs.centroid

        # Paparan Metrik
        c1, c2 = st.columns(2)
        c1.metric("Luas (Meter Persegi)", f"{poly_original.area:.3f} m²")
        c2.metric("Luas (Ekar)", f"{(poly_original.area * 0.000247105):.4f} ac")

        # Peta
        m = folium.Map(location=[centroid.y, centroid.x], zoom_start=20, tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google Satellite")

        # Lukis Lot
        folium.Polygon(locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords], color="cyan", weight=2, fill=True, fill_opacity=0.1).add_to(m)

        for i, row in df.iterrows():
            p_curr = poly_wgs.exterior.coords[i]
            p_next = poly_wgs.exterior.coords[(i+1)%len(df)]
            
            # 1. Label Stesen (Pink)
            folium.Marker([p_curr[1], p_curr[0]], icon=folium.DivIcon(html=f'<div style="color:magenta; font-weight:bold; font-size:10pt;">{row["STN"]}</div>')).add_to(m)

            # 2. Label Bearing & Jarak (Selari/Senget)
            mid_lat = (p_curr[1] + p_next[1]) / 2
            mid_lon = (p_curr[0] + p_next[0]) / 2
            
            # Offset ke luar sedikit
            off_lat = mid_lat + (mid_lat - centroid.y) * 0.15
            off_lon = mid_lon + (mid_lon - centroid.x) * 0.15

            # CSS Transform Rotate digunakan untuk sengetkan teks
            label_html = f"""
                <div style="
                    transform: rotate({row['Rotation']}deg); 
                    white-space: nowrap; 
                    text-align: center;
                    background-color: rgba(0,0,0,0.4);
                    padding: 2px;
                    border-radius: 3px;
                ">
                    <div style="font-size: 8pt; color: yellow; font-weight: bold;">{row['Bearing']}</div>
                    <div style="font-size: 8pt; color: white;">{row['Jarak']}m</div>
                </div>"""
            
            folium.Marker([off_lat, off_lon], icon=folium.DivIcon(html=label_html)).add_to(m)

        st_folium(m, use_container_width=True, height=600)
    else:
        st.error("Sila pastikan kolum E, N, dan STN wujud dalam CSV.")
