import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from folium.plugins import MeasureControl, MousePosition, Fullscreen
from streamlit_folium import st_folium
import numpy as np

# --- 1. PENGURUSAN LOGIN ---
ALLOWED_IDS = ["MUHAMMAD", "NAFIZ", "NAJMI"]

if 'password_db' not in st.session_state:
    st.session_state['password_db'] = 'admin123'
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_page():
    st.title("🔐 Sistem Surveyor WebGIS")
    user_id = st.selectbox("Pilih ID Pengguna", ALLOWED_IDS)
    pwd = st.text_input("Kata Laluan", type="password")
    col1, col2 = st.columns(2)
    if col1.button("Login"):
        if pwd == st.session_state['password_db']:
            st.session_state['logged_in'] = True
            st.session_state['current_user'] = user_id
            st.rerun()
        else:
            st.error("Kata laluan salah!")
    if col2.button("Lupa Password?"):
        st.session_state['reset_mode'] = True
    if st.session_state.get('reset_mode'):
        new_pwd = st.text_input("Masukkan Password Baru")
        if st.button("Simpan Password Baru"):
            st.session_state['password_db'] = new_pwd
            st.session_state['reset_mode'] = False
            st.success("Password baru disimpan!")

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
        p1 = df.iloc[i]
        p2 = df.iloc[(i + 1) % len(df)]
        mid_e, mid_n = (p1['E'] + p2['E']) / 2, (p1['N'] + p2['N']) / 2
        dx, dy = p2['E'] - p1['E'], p2['N'] - p1['N']
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing = decimal_to_dms((np.degrees(angle_rad) + 360) % 360)
        rotation = np.degrees(angle_rad) - 90
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
        
        v_e, v_n = mid_e - centroid.x, mid_n - centroid.y
        v_mag = np.sqrt(v_e**2 + v_n**2)
        off_e = mid_e + (v_e / v_mag * offset_dist)
        off_n = mid_n + (v_n / v_mag * offset_dist)
        
        stn_v_e, stn_v_n = p1['E'] - centroid.x, p1['N'] - centroid.y
        stn_v_mag = np.sqrt(stn_v_e**2 + stn_v_n**2)
        stn_off_e = p1['E'] + (stn_v_e / stn_v_mag * 1.5)
        stn_off_n = p1['N'] + (stn_v_n / stn_v_mag * 1.5)
        
        results.append({
            'dari_stn': p1['STN'], 'ke_stn': p2['STN'],
            'bearing': bearing, 'distance': f"{dist:.3f}m", 
            'rotation': rotation, 'off_e': off_e, 'off_n': off_n, 
            'stn_off_e': stn_off_e, 'stn_off_n': stn_off_n
        })
    return results

# --- 3. MAIN APP ---
if not st.session_state['logged_in']:
    login_page()
else:
    st.set_page_config(page_title="Surveyor Pro WebGIS", layout="wide")
    st.title("🛰️ Johor Grid WebGIS (EPSG:4390)")

    with st.sidebar:
        st.markdown(f"### 👋 Hi, **{st.session_state['current_user']}**")
        if st.sidebar.button("Log Keluar"):
            st.session_state['logged_in'] = False
            st.rerun()

        st.header("⚙️ Tetapan Visual")
        show_poly = st.checkbox("Sempadan Lot", value=True)
        show_stn_point = st.checkbox("Titik Batu Sempadan", value=True)
        show_labels = st.checkbox("Bearing & Jarak", value=True)
        show_area = st.checkbox("Luas & Perimeter", value=True)
        text_size = st.slider("Saiz Teks Label", 6, 20, 10)
        offset_val = st.slider("Jarak Label Garisan (m)", 0.1, 10.0, 1.8)
        
        st.header("📂 Data & Export")
        uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        area_val = poly_meter.area
        peri_val = poly_meter.length
        label_data = calculate_survey_labels(df, poly_meter, offset_val)
        
        # Sediakan GeoDataFrame untuk Export & Paparan
        gdf_poly = gpd.GeoDataFrame({
            'User': [st.session_state['current_user']],
            'Luas_m2': [round(area_val, 3)],
            'Perimeter_m': [round(peri_val, 3)],
            'Label_QGIS': [f"Luas: {area_val:.2f}m2 | Peri: {peri_val:.2f}m"]
        }, crs="EPSG:4390", geometry=[poly_meter]).to_crs(epsg=4326)
        
        poly_wgs = gdf_poly.geometry.iloc[0]

        # DOWNLOAD BUTTON
        st.sidebar.download_button("📥 Export GeoJSON (QGIS)", gdf_poly.to_json(), f"lot_{st.session_state['current_user']}.geojson", "application/json", use_container_width=True)

        # MAP DISPLAY
        m = folium.Map(location=[poly_wgs.centroid.y, poly_wgs.centroid.x], zoom_start=19, max_zoom=24)
        folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Satellite", max_zoom=24, max_native_zoom=20).add_to(m)

        # 1. Plot Poligon
        if show_poly:
            folium.Polygon(locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords], color="#00FFFF", weight=2, fill=True, fill_opacity=0.1).add_to(m)

        # 2. Plot Titik Sempadan Interaktif
        if show_stn_point:
            for i, row in df.iterrows():
                coords_wgs = poly_wgs.exterior.coords[i]
                popup_content = f"""
                <div style='font-family: Arial; min-width: 150px;'>
                    <b style='color: #e74c3c;'>Batu Sempadan: {row['STN']}</b><br><hr>
                    <b>Easting (E):</b> {row['E']:.3f}<br>
                    <b>Northing (N):</b> {row['N']:.3f}
                </div>
                """
                folium.CircleMarker(
                    location=[coords_wgs[1], coords_wgs[0]],
                    radius=6, color="red", fill=True, fill_color="white", fill_opacity=1.0,
                    popup=folium.Popup(popup_content, max_width=300)
                ).add_to(m)

        # 3. Plot Label Luas/Perimeter Tengah
        if show_area:
            area_html = f"""<div style="font-size:{text_size+2}pt; color:#00FF00; font-weight:bold; text-shadow:2px 2px 4px black; text-align:center; transform:translate(-50%,-50%); width:200px;">
            {area_val:.3f} m²<br><span style="font-size:{text_size}pt; color:#FFA500;">P: {peri_val:.3f} m</span></div>"""
            folium.Marker([poly_wgs.centroid.y, poly_wgs.centroid.x], icon=folium.DivIcon(html=area_html)).add_to(m)

        # 4. Plot Bearing & Jarak
        if show_labels:
            off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
            gdf_off_wgs = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:4390").to_crs(epsg=4326)
            for i, data in enumerate(label_data):
                pos_wgs = gdf_off_wgs.iloc[i].geometry
                lbl = f'<div style="transform:translate(-50%,-50%) rotate({data["rotation"]}deg); text-align:center; font-size:{text_size}pt; color:yellow; font-weight:bold; text-shadow:2px 2px black;">{data["bearing"]}<br>{data["distance"]}</div>'
                folium.Marker([pos_wgs.y, pos_wgs.x], icon=folium.DivIcon(html=lbl)).add_to(m)

        Fullscreen().add_to(m)
        st_folium(m, use_container_width=True, height=650)

        # --- 4. JADUAL MAKLUMAT DI BAWAH PETA ---
        st.markdown("---")
        st.subheader("📋 Ringkasan Maklumat Lot & Sempadan")
        
        col_tab1, col_tab2 = st.columns([1, 2])
        
        with col_tab1:
            st.write("**Statistik Lot**")
            summary_df = pd.DataFrame({
                "Parameter": ["Keluasan", "Perimeter", "Bilangan Stesen"],
                "Nilai": [f"{area_val:.3f} m²", f"{peri_val:.3f} m", len(df)]
            })
            st.table(summary_df)

        with col_tab2:
            st.write("**Data Ukuran (Bearing & Jarak)**")
            data_list = [{"Dari": x['dari_stn'], "Ke": x['ke_stn'], "Bearing": x['bearing'], "Jarak": x['distance']} for x in label_data]
            st.dataframe(pd.DataFrame(data_list), use_container_width=True, height=200)

        st.write("**Koordinat Stesen (Johor Grid EPSG:4390)**")
        st.dataframe(df[['STN', 'E', 'N']], use_container_width=True)

    else:
        st.info("Sila muat naik fail CSV untuk memaparkan lot.")
