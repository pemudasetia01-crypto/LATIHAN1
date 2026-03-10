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
    if s >= 60: m += 1; s = 0
    return f"{d}°{abs(m)}'{abs(s)}\""

# --- 2. FUNGSI KIRA DATA UKUR & POSISI LABEL ---
def calculate_survey_labels(df):
    results = []
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing_deg = (np.degrees(angle_rad) + 360) % 360
        
        # Rotasi teks: Selari dengan garisan
        rotation = np.degrees(angle_rad) - 90
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
        
        # Pengiraan Offset (Normal Vector ke luar)
        # Kita ambil arah 90 darjah dari garisan
        perp_angle = angle_rad - (np.pi / 2)
        # Jarak offset (dalam meter koordinat asal)
        offset_val = 1.5 # 1.5 meter keluar dari garisan
        off_e = ((p1['E'] + p2['E']) / 2) + (np.sin(perp_angle) * offset_val)
        off_n = ((p1['N'] + p2['N']) / 2) + (np.cos(perp_angle) * offset_val)
        
        results.append({
            'bearing': decimal_to_dms(bearing_deg),
            'distance': round(dist, 3),
            'rotation': rotation,
            'off_e': off_e,
            'off_n': off_n
        })
    return results

# --- 3. UI STREAMLIT ---
st.set_page_config(page_title="Surveyor WebGIS Pro", layout="wide")
st.title("🗺️ WebGIS Poligon: Label Luar & Rapat Garisan")

uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if all(col in df.columns for col in ['E', 'N', 'STN']):
        
        # Kira Data Label
        label_data = calculate_survey_labels(df)
        
        # Geoprocessing (EPSG 3375 untuk Semenanjung)
        poly_coords = list(zip(df['E'], df['N']))
        poly_meter = Polygon(poly_coords)
        gdf_wgs = gpd.GeoDataFrame(index=[0], crs="EPSG:3375", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_wgs.geometry.iloc[0]
        
        # Tukar koordinat offset ke WGS84 untuk paparan peta
        off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
        gdf_off = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:3375").to_crs(epsg=4326)

        # Metrik Luas
        st.metric("Luas Lot", f"{poly_meter.area:.3f} m² ({(poly_meter.area * 0.0002471):.4f} Ekar)")

        # Konfigurasi Peta
        m = folium.Map(location=[poly_wgs.centroid.y, poly_wgs.centroid.x], zoom_start=20, max_zoom=22)
        folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", max_zoom=22, max_native_zoom=20).add_to(m)

        # Lukis Lot
        folium.Polygon(locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords], color="#00FFFF", weight=2, fill=True, fill_opacity=0.1).add_to(m)

        # Tambah Label
        for i, row in df.iterrows():
            # Label Stesen
            folium.CircleMarker([poly_wgs.exterior.coords[i][1], poly_wgs.exterior.coords[i][0]], 
                                radius=3, color="red", fill=True).add_to(m)
            
            # Label Bearing & Jarak
            data = label_data[i]
            pos = gdf_off.iloc[i].geometry
            
            label_html = f"""
                <div style="
                    transform: rotate({data['rotation']}deg); 
                    text-align: center; 
                    white-space: nowrap;
                    pointer-events: none;
                ">
                    <div style="font-size: 8pt; color: #FFFF00; font-weight: bold; text-shadow: 1px 1px 2px black;">{data['bearing']}</div>
                    <div style="font-size: 7pt; color: #FFFFFF; font-weight: bold; text-shadow: 1px 1px 2px black;">{data['distance']}m</div>
                </div>"""
            
            folium.Marker([pos.y, pos.x], icon=folium.DivIcon(html=label_html)).add_to(m)

        st_folium(m, use_container_width=True, height=700)
    else:
        st.error("Fail CSV mesti mengandungi kolum STN, E, dan N.")
