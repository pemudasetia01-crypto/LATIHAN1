import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Visualisasi Data Ukur", layout="centered")

st.title("🗺️ Plot Poligon Data Ukur")
st.write("Unggah file CSV Anda untuk melihat visualisasi poligon berdasarkan koordinat E dan N.")

# 1. Upload File
uploaded_file = st.file_uploader("Pilih file CSV", type="csv")

if uploaded_file is not None:
    # Membaca data
    df = pd.read_csv(uploaded_file)
    
    st.subheader("Pratinjau Data")
    st.write(df.head())

    # Memastikan kolom yang dibutuhkan ada
    if 'E' in df.columns and 'N' in df.columns:
        
        # 2. Logika Poligon
        # Untuk menutup poligon, kita tambahkan titik pertama ke baris terakhir
        df_poly = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        
        # 3. Visualisasi dengan Matplotlib
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Plot garis poligon
        ax.plot(df_poly['E'], df_poly['N'], marker='o', linestyle='-', color='b', label='Batas Lahan')
        
        # Tambahkan label untuk setiap STN (Stasiun)
        for i, row in df.iterrows():
            ax.text(row['E'], row['N'], f" {int(row['STN'])}", fontsize=12, verticalalignment='bottom')

        ax.set_xlabel('Easting (E)')
        ax.set_ylabel('Northing (N)')
        ax.set_title('Visualisasi Poligon Koordinat')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.set_aspect('equal', adjustable='box') # Penting agar skala X dan Y seimbang
        
        # Tampilkan di Streamlit
        st.pyplot(fig)
        
        st.success("Poligon berhasil digambarkan!")
    else:
        st.error("Pastikan file CSV memiliki kolom 'E' dan 'N'.")