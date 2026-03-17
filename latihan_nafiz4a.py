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
        results.append({'bearing': bearing, 'distance': f"{dist:.3f}m", 'rotation': rotation, 'off_e': off_e, 'off_n': off_n, 'stn_off_e': stn_off_e, 'stn_off_n': stn_off_n})
    return results

# --- 3. MAIN APP ---
if not st.session_state['logged_in']:
    login_page()
else:
    st.set_page_config(page_title="Surveyor Pro WebGIS", layout="wide")
    
    with st.sidebar:
        logo_url = 'https://imgur.com/your_po_logo_here.png' 
        try:
            st.image('image_0.png', use_container_width=True)
        except:
            st.image(logo_url, use_container_width=True)

        st.markdown(f"### 👋 Hi, **{st.session_state['current_user']}**")
        if st.sidebar.button("Log Keluar"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.title("🛰️ Johor Grid WebGIS (EPSG:4390)")

    with st.sidebar:
        st.header("⚙️ Tetapan Visual")
        show_poly = st.checkbox("Sempadan Lot", value=True)
        show_stn_point = st.checkbox("Titik Batu Sempadan", value=True)
        show_stn_no = st.checkbox("No. Stesen", value=True)
        show_labels = st.checkbox("Bearing & Jarak", value=True)
        show_area = st.checkbox("Luas Lot", value=True)
        st.markdown("---")
        text_size = st.slider("Saiz Teks Label", 6, 20, 10)
        marker_size = st.slider("Saiz Titik", 2, 12, 6)
        offset_val = st.slider("Jarak Label Garisan (m)", 0.1, 10.0, 1.8)
        st.header("📂 Data & Export")
        uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")
        export_container = st.container()

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        label_data = calculate_survey_labels(df, poly_meter, offset_val)
        gdf_poly = gpd.GeoDataFrame(index=[0], crs="EPSG:4390", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_poly.geometry.iloc[0]
        
        off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
        gdf_off_wgs = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:4390").to_crs(epsg=4326)
        stn_off_df = pd.DataFrame([{'E': x['stn_off_e'], 'N': x['stn_off_n']} for x in label_data])
        gdf_stn_off_wgs = gpd.GeoDataFrame(stn_off_df, geometry=gpd.points_from_xy(stn_off_df.E, stn_off_df.N), crs="EPSG:4390").to_crs(epsg=4326)

        with export_container:
            st.download_button("📥 Export GeoJSON (QGIS)", gdf_poly.to_json(), f"lot_{st.session_state['current_user']}.geojson", "application/json", use_container_width=True)

        m = folium.Map(location=[poly_wgs.centroid.y, poly_wgs.centroid.x], zoom_start=19, max_zoom=22)
        folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Satellite", max_zoom=22, max_native_zoom=20).add_to(m)

        # 1. Sempadan
        if show_poly:
            folium.Polygon(locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords], color="#00FFFF", weight=2, fill=True, fill_opacity=0.1, popup=f"Luas: {poly_meter.area:.3f} m²").add_to(m)

        # 2. Batu Sempadan
        for i, row in df.iterrows():
            coords_wgs = poly_wgs.exterior.coords[i]
            if show_stn_point:
                popup_info = f"<div style='min-width:150px;'><b style='color:red;'>STN {row['STN']}</b><hr><b>E:</b> {row['E']:.3f}<br><b>N:</b> {row['N']:.3f}</div>"
                folium.CircleMarker(location=[coords_wgs[1], coords_wgs[0]], radius=marker_size, color="red", fill=True, fill_opacity=0.8, tooltip=f"STN: {row['STN']}", popup=folium.Popup(popup_info, max_width=300)).add_to(m)
            
            if show_stn_no:
                stn_pos = gdf_stn_off_wgs.iloc[i].geometry
                stn_html = f'<div style="font-size: {text_size}pt; color: white; font-weight: bold; text-shadow: 2px 2px 3px black; transform: translate(-50%, -50%);">{row["STN"]}</div>'
                folium.Marker([stn_pos.y, stn_pos.x], icon=folium.DivIcon(html=stn_html)).add_to(m)

        # 3. Bearing di ATAS, Jarak di BAWAH
        if show_labels:
            for i, data in enumerate(label_data):
                pos_wgs = gdf_off_wgs.iloc[i].geometry
                label_html = f"""
                <div style="
                    transform: translate(-50%, -50%) rotate({data['rotation']}deg); 
                    text-align: center; white-space: nowrap; pointer-events: none;
                ">
                    <div style="
                        font-size: {text_size}pt; color: #FFFF00; font-weight: bold; 
                        text-shadow: 2px 2px 5px black;
                        display: block; /* Memastikan bearing di baris tersendiri */
                    ">{data['bearing']}</div>
                    <div style="
                        font-size: {text_size-1}pt; color: #FFFFFF; font-weight: bold; 
                        text-shadow: 2px 2px 5px black;
                        display: block; /* Memastikan jarak di bawah bearing */
                        margin-top: -2px; /* Rapatkan sedikit jarak antara baris */
                    ">{data['distance']}</div>
                </div>"""
                folium.Marker([pos_wgs.y, pos_wgs.x], icon=folium.DivIcon(html=label_html)).add_to(m)

        # 4. Luas
        if show_area:
            area_text = f"{poly_meter.area:.3f} m²"
            folium.Marker([poly_wgs.centroid.y, poly_wgs.centroid.x], icon=folium.DivIcon(html=f'<div style="font-size: {text_size+3}pt; color: #00FF00; font-weight: bold; text-shadow: 3px 3px 6px black; text-align: center; width: 200px; transform: translate(-50%,-50%); line-height: 1.2;">{area_text}</div>')).add_to(m)

        Fullscreen().add_to(m)
        MeasureControl(primary_length_unit='meters').add_to(m)
        MousePosition().add_to(m)
        st_folium(m, use_container_width=True, height=700)
    else:
        st.info("Sila muat naik fail CSV di bahagian sidebar.")
