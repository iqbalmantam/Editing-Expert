import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import pandas as pd
import os
import tempfile
import io

st.set_page_config(page_title="Smart Hybrid Font Receipt Editor", layout="wide")

# Menyembunyikan Header, Footer, dan Menu bawaan Streamlit (termasuk ikon GitHub)
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🌐 Smart Hybrid Font Digital Receipt Editor")
st.markdown("Sistem pemindaian cerdas yang mendeteksi pustaka font di GitHub, dengan opsi unggah lokal otomatis jika tidak tersedia.")

# 1. Pengecekan Pustaka Font di GitHub
FONT_DIR = "fonts"
github_fonts = {}
if os.path.exists(FONT_DIR) and os.path.isdir(FONT_DIR):
    for root, dirs, files in os.walk(FONT_DIR):
        for file in files:
            if file.endswith(".ttf"):
                full_path = os.path.join(root, file)
                display_name = os.path.relpath(full_path, FONT_DIR)
                github_fonts[display_name] = full_path

# Membuat daftar pilihan font (Gabungan GitHub + Opsi Lokal)
font_options = list(github_fonts.keys())
font_options.append("➕ Unggah Font Baru dari Komputer (Lokal)")

selected_font_option = st.selectbox("Pilih Jenis Font:", font_options)

font_path = None
if selected_font_option == "➕ Unggah Font Baru dari Komputer (Lokal)":
    local_font_file = st.file_uploader("📂 Unggah file font (.ttf) dari komputer Anda:", type=["ttf"])
    if local_font_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp_font:
            tmp_font.write(local_font_file.getvalue())
            font_path = tmp_font.name
else:
    if selected_font_option in github_fonts:
        font_path = github_fonts[selected_font_option]

# 2. Unggah Gambar Tangkapan Layar
uploaded_file = st.file_uploader("🖼️ Unggah Tangkapan Layar Bukti Transaksi (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    width, height = image.size
    
    with st.spinner("Memindai struktur layout dan token teks secara cerdas..."):
        ocr_df = pytesseract.image_to_data(image, output_type=pytesseract.Output.DATAFRAME)
        ocr_df = ocr_df[ocr_df.text.notnull() & ocr_df.text.str.strip().astype(bool)].reset_index(drop=True)
        
        lines = []
        current_line = []
        last_y = -1
        
        for _, row in ocr_df.sort_values(by=['top', 'left']).iterrows():
            y = row['top']
            if last_y == -1 or abs(y - last_y) > 12:
                if current_line:
                    lines.append(current_line)
                current_line = [row]
            else:
                current_line.append(row)
            last_y = y
        if current_line:
            lines.append(current_line)
            
        grouped_lines = []
        for line_items in lines:
            texts = [str(item['text']).strip() for item in line_items if str(item['text']).strip()]
            if not texts:
                continue
            combined_text = " ".join(texts)
            min_left = min(item['left'] for item in line_items)
            min_top = min(item['top'] for item in line_items)
            max_right = max(item['left'] + item['width'] for item in line_items)
            max_bottom = max(item['top'] + item['height'] for item in line_items)
            
            grouped_lines.append({
                'text': combined_text,
                'left': min_left,
                'top': min_top,
                'width': max_right - min_left,
                'height': max_bottom - min_top
            })
            
        line_df = pd.DataFrame(grouped_lines)

    st.markdown("**1. Daftar Baris Teks Terdeteksi**")
    if len(line_df) > 0:
        st.dataframe(line_df[['text', 'left', 'top', 'width', 'height']], use_container_width=True)

        st.markdown("**2. Masukkan Teks Baru**")
        selected_index = st.number_input(
            "Pilih Baris Index yang Ingin Diubah:", 
            min_value=0, 
            max_value=len(line_df)-1, 
            value=0, 
            step=1
        )
        
        target_row = line_df.iloc[selected_index]
        st.info(f"Baris Terpilih: **'{target_row['text']}'**")
        
        new_text = st.text_input("Teks/Nominal Baru:", value=target_row['text'])

        if st.button("✨ Eksekusi Auto-Manipulasi Sempurna"):
            edited_image = image.copy()
            draw = ImageDraw.Draw(edited_image)
            
            x = int(target_row['left'])
            y = int(target_row['top'])
            w = int(target_row['width'])
            h = int(target_row['height'])
            
            # Ukuran font otomatis proporsional berdasarkan tinggi baris asli
            font_size = max(14, int(h * 0.9))
            
            try:
                if font_path:
                    font = ImageFont.truetype(font_path, size=font_size)
                else:
                    font = ImageFont.load_default()
                    st.warning("⚠️ Belum ada font yang dipilih atau diunggah. Menggunakan font default sistem.")
            except Exception:
                font = ImageFont.load_default()
                
            dummy_draw = ImageDraw.Draw(edited_image)
            try:
                text_bbox = dummy_draw.textbbox((0, 0), new_text, font=font)
                new_text_w = text_bbox[2] - text_bbox[0]
            except Exception:
                new_text_w = len(new_text) * (font_size * 0.5)
                
            total_clean_w = max(w, int(new_text_w)) + 25
            
            box_coords = (
                max(0, x - 5), 
                max(0, y - 4), 
                min(width, x + total_clean_w), 
                min(height, y + h + 6)
            )
            
            try:
                sample_color = image.getpixel((max(0, x - 5), y + (h // 2)))
            except Exception:
                sample_color = (255, 255, 255)
                
            draw.rectangle(box_coords, fill=sample_color)
            
            text_color = (24, 34, 54) # Warna standar teks perbankan digital
            
            draw.text((x, y), new_text, fill=text_color, font=font)
            
            st.markdown("**🎯 Hasil Tangkapan Layar Termodifikasi Sempurna**")
            st.image(edited_image, use_container_width=True)
            
            buf = io.BytesIO()
            edited_image.save(buf, format="PNG")
            st.download_button(
                label="📥 Unduh Hasil Manipulasi (PNG)",
                data=buf.getvalue(),
                file_name="master_receipt_edited.png",
                mime="image/png"
            )
    else:
        st.warning("Tidak ada baris teks yang terdeteksi.")
else:
    st.info("Silakan unggah tangkapan layar bukti transaksi untuk memulai.")