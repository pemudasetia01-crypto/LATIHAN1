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

# --- 2. FUNGSI KIRA DATA UKUR & POSISI LABEL (SMART OFFSET) ---
def calculate_survey_labels(df, poly_meter):
    results = []
    centroid = poly_meter.centroid
    
    for i in range(len(df)):
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        
        mid_e = (p1['E'] + p2['E']) / 2
        mid_n = (p1['N'] + p2['N']) / 2
        
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing_deg = (np.degrees(angle_rad) + 360) % 360
        
        # Rotasi teks
        rotation = np.degrees(angle_rad) - 90
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
        
        # Tolak label ke luar dari centroid
        vec_c_to_m_e = mid_e - centroid.x
        vec_c_to_m_n = mid_n - centroid.y
        mag = np.sqrt(vec_c_to_m_e**2 + vec_c_to_m_n**2)
        
        offset_val = 2.0  # Jarak label dari garisan (meter)
        off_e = mid_e + (vec_c_to_m_e / mag * offset_val)
        off_n = mid_n + (vec_c_to_m_n / mag * offset_val)
        
        results.append({
            'bearing': decimal_to_dms(bearing_deg),
            'distance': f"{dist:.3f}m",
            'rotation': rotation,
            'off_e': off_e,
            'off_n': off_n
        })
    return results

# --- 3. UI STREAMLIT ---
st.set_page_config(page_title="Surveyor WebGIS Johor", layout="wide")
st.title("🗺️ WebGIS Poligon: Kertau/Johor (EPSG:4390) ke WGS84")
st.info("Sistem ini menukar koordinat EPSG:4390 secara automatik ke WGS84 untuk paparan Google Satellite.")

uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if all(col in df.columns for col in ['E', 'N', 'STN']):
        
        # 1. Bina Poligon dalam koordinat asal (EPSG:4390)
        poly_coords = list(zip(df['E'], df['N']))
        poly_meter = Polygon(poly_coords)
        
        # 2. Kira Data Label (Bearing/Jarak) menggunakan data meter
        label_data = calculate_survey_labels(df, poly_meter)
        
        # 3. AUTO-CONVERT: Tukar Poligon ke WGS84 (EPSG:4326)
        gdf_poly = gpd.GeoDataFrame(index=[0], crs="EPSG:4390", geometry=[poly_meter])
        gdf_poly_wgs = gdf_poly.to_crs(epsg=4326)
        poly_wgs = gdf_poly_wgs.geometry.iloc[0]
        
        # 4. AUTO-CONVERT: Tukar Titik Offset Label ke WGS84
        off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
        gdf_off = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:4390")
        gdf_off_wgs = gdf_off.to_crs(epsg=4326)

        # Paparan Metrik
        col1, col2 = st.columns(2)
        col1.metric("Luas Lot", f"{poly_meter.area:.3f} m²")
        col2.metric("Luas (Ekar)", f"{(poly_meter.area * 0.0002471):.4f} Ekar")

        # 5. KONFIGURASI PETA FOLIUM
        m = folium.Map(
            location=[poly_wgs.centroid.y, poly_wgs.centroid.x], 
            zoom_start=19, 
            max_zoom=22
        )
        
        # Tambah Layer Google Satellite
        google_sat = folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google Satellite",
            name="Google Satellite",
            max_zoom=22,
            max_native_zoom=20
        ).add_to(m)

        # Lukis sempadan Poligon
        folium.Polygon(
            locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords],
            color="#00FFFF",
            weight=3,
            fill=True,
            fill_opacity=0.15
        ).add_to(m)

        # Tambah Marker Stesen & Label
        for i, row in df.iterrows():
            # Marker Merah di Stesen
            stn_coord_wgs = poly_wgs.exterior.coords[i]
            folium.CircleMarker(
                [stn_coord_wgs[1], stn_coord_wgs[0]], 
                radius=4, color="red", fill=True, popup=f"STN: {row['STN']}"
            ).add_to(m)
            
            # Label Bearing & Jarak (HTML)
            data = label_data[i]
            pos_wgs = gdf_off_wgs.iloc[i].geometry
            
            label_html = f"""
                <div style="
                    transform: translate(-50%, -50%) rotate({data['rotation']}deg); 
                    text-align: center; 
                    white-space: nowrap;
                    pointer-events: none;
                ">
                    <div style="font-size: 8pt; color: #FFFF00; font-weight: bold; text-shadow: 2px 2px 3px black;">{data['bearing']}</div>
                    <div style="font-size: 7pt; color: #FFFFFF; font-weight: bold; text-shadow: 2px 2px 3px black;">{data['distance']}</div>
                </div>"""
            
            folium.Marker(
                [pos_wgs.y, pos_wgs.x], 
                icon=folium.DivIcon(html=label_html)
            ).add_to(m)

        # Paparkan Peta
        st_folium(m, use_container_width=True, height=700)
        
    else:
        st.error("Ralat: Fail CSV mesti mempunyai kolum 'STN', 'E', dan 'N'.")
