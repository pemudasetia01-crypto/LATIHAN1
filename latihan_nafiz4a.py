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
        
        # Titik tengah garisan (Midpoint)
        mid_e = (p1['E'] + p2['E']) / 2
        mid_n = (p1['N'] + p2['N']) / 2
        
        # Jarak dan Bearing
        dx = p2['E'] - p1['E']
        dy = p2['N'] - p1['N']
        dist = np.sqrt(dx**2 + dy**2)
        angle_rad = np.arctan2(dx, dy)
        bearing = decimal_to_dms((np.degrees(angle_rad) + 360) % 360)
        
        # Rotasi Teks: Selari dengan garisan
        rotation = np.degrees(angle_rad) - 90
        if rotation > 90: rotation -= 180
        if rotation < -90: rotation += 180
        
        # --- LOGIK TOLAK KE LUAR ---
        # 1. Dapatkan vektor dari centroid ke midpoint
        v_e = mid_e - centroid.x
        v_n = mid_n - centroid.y
        # 2. Tukarkan kepada unit vektor (normalisasi)
        v_mag = np.sqrt(v_e**2 + v_n**2)
        unit_v_e = v_e / v_mag
        unit_v_n = v_n / v_mag
        
        # 3. Tentukan koordinat label (midpoint + vektor ke luar * offset)
        off_e = mid_e + (unit_v_e * offset_dist)
        off_n = mid_n + (unit_v_n * offset_dist)
        
        results.append({
            'bearing': bearing, 
            'distance': f"{dist:.3f}m", 
            'rotation': rotation, 
            'off_e': off_e, 
            'off_n': off_n
        })
    return results

# --- 3. MAIN APP ---
if not st.session_state['logged_in']:
    login_page()
else:
    st.set_page_config(page_title="Surveyor Pro WebGIS", layout="wide")
    st.sidebar.markdown(f"### 👋 Hi, **{st.session_state['current_user']}**")
    if st.sidebar.button("Log Keluar"):
        st.session_state['logged_in'] = False
        st.rerun()

    st.title("🛰️ Johor Grid WebGIS (EPSG:4390)")

    with st.sidebar:
        st.header("⚙️ Tetapan Visual")
        show_poly = st.checkbox("Paparkan Sempadan Lot", value=True)
        show_stn = st.checkbox("Paparkan Titik Stesen", value=True)
        show_labels = st.checkbox("Paparkan Bearing/Jarak", value=True)
        show_area = st.checkbox("Paparkan Label Luas", value=True)
        
        st.markdown("---")
        text_size = st.slider("Saiz Teks Label", 6, 20, 9)
        marker_size = st.slider("Saiz Titik Stesen", 2, 12, 5)
        offset_val = st.slider("Jarak Offset Label (m)", 0.1, 10.0, 1.5) # Dikecilkan default ke 1.5m
        
        st.header("📂 Data & Export")
        uploaded_file = st.file_uploader("Muat naik CSV (STN, E, N)", type="csv")
        export_container = st.container()

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        # Pastikan data ikut urutan untuk membentuk poligon
        poly_meter = Polygon(list(zip(df['E'], df['N'])))
        
        # Pengiraan label dengan logik "Push-Out"
        label_data = calculate_survey_labels(df, poly_meter, offset_val)
        
        # Convert ke WGS84 untuk paparan peta
        gdf_poly = gpd.GeoDataFrame(index=[0], crs="EPSG:4390", geometry=[poly_meter]).to_crs(epsg=4326)
        poly_wgs = gdf_poly.geometry.iloc[0]
        
        off_df = pd.DataFrame([{'E': x['off_e'], 'N': x['off_n']} for x in label_data])
        gdf_off_wgs = gpd.GeoDataFrame(off_df, geometry=gpd.points_from_xy(off_df.E, off_df.N), crs="EPSG:4390").to_crs(epsg=4326)

        with export_container:
            st.download_button(
                label="📥 Export GeoJSON (QGIS)",
                data=gdf_poly.to_json(),
                file_name=f"lot_{st.session_state['current_user']}.geojson",
                mime="application/json",
                use_container_width=True
            )

        m = folium.Map(location=[poly_wgs.centroid.y, poly_wgs.centroid.x], zoom_start=19, max_zoom=22)
        
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google", name="Google Satellite", max_zoom=22, max_native_zoom=20
        ).add_to(m)

        # 1. Sempadan
        if show_poly:
            folium.Polygon(
                locations=[[p[1], p[0]] for p in poly_wgs.exterior.coords],
                color="#00FFFF", weight=2, fill=True, fill_opacity=0.1,
                popup=f"Luas: {poly_meter.area:.3f} m²"
            ).add_to(m)

        # 2. Titik Stesen
        if show_stn:
            for i, row in df.iterrows():
                coords_wgs = poly_wgs.exterior.coords[i]
                folium.CircleMarker(
                    [coords_wgs[1], coords_wgs[0]], radius=marker_size, color="red", fill=True,
                    popup=f"STN: {row['STN']}<br>E: {row['E']}<br>N: {row['N']}"
                ).add_to(m)

        # 3. Label Bearing/Jarak (Tengah Garisan & Di Luar)
        if show_labels:
            for i, data in enumerate(label_data):
                pos_wgs = gdf_off_wgs.iloc[i].geometry
                # CSS translate(-50%, -50%) untuk pastikan center tepat pada koordinat
                label_html = f"""<div style="
                    transform: translate(-50%, -50%) rotate({data['rotation']}deg); 
                    text-align: center; 
                    white-space: nowrap;
                    pointer-events: none;">
                    <div style="
                        font-size: {text_size}pt; 
                        color: #00FF00; 
                        font-weight: bold; 
                        text-shadow: 1px 1px 2px #000;
                        line-height: 1.1;">
                        {data['bearing']}<br>{data['distance']}
                    </div>
                </div>"""
                folium.Marker([pos_wgs.y, pos_wgs.x], icon=folium.DivIcon(html=label_html)).add_to(m)

        # 4. Label Luas
        if show_area:
            area_text = f"{poly_meter.area:.3f} m²"
            folium.Marker(
                [poly_wgs.centroid.y, poly_wgs.centroid.x],
                icon=folium.DivIcon(html=f"""<div style="
                    font-size: {text_size+2}pt; 
                    color: yellow; 
                    font-weight: bold; 
                    text-shadow: 2px 2px 4px black; 
                    text-align: center; 
                    width: 200px; 
                    transform: translate(-50%,-50%);">
                    {area_text}
                </div>""")
            ).add_to(m)

        Fullscreen().add_to(m)
        MeasureControl(primary_length_unit='meters').add_to(m)
        MousePosition().add_to(m)
        st_folium(m, use_container_width=True, height=700)
    else:
        st.info("Sila muat naik fail CSV di bahagian sidebar.")
