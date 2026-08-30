import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import pandas as pd
import os
import io
import tempfile

st.set_page_config(page_title="BCA Auto-Perfect Editor", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("**🌐 BCA Auto-Perfect Digital Receipt Editor**")
st.markdown("Sistem render font otomatis murni tanpa pengaturan jarak manual. Bersih, cepat, dan proporsional.")

# --- MANAJEMEN FONT OTOMATIS ---
FONT_DIR = "fonts"
github_fonts = {}
if os.path.exists(FONT_DIR) and os.path.isdir(FONT_DIR):
    for root, dirs, files in os.walk(FONT_DIR):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".otf"):
                full_path = os.path.join(root, file)
                display_name = os.path.relpath(full_path, FONT_DIR)
                github_fonts[display_name] = full_path

# Urutkan font non-italic ke atas
sorted_font_names = sorted(github_fonts.keys(), key=lambda name: ("italic" in name.lower(), name))
font_options = sorted_font_names
font_options.append("➕ Unggah Font Baru dari Komputer (Lokal)")

selected_font_option = st.selectbox("Pilih Jenis Font (Sangat disarankan: Roboto-Bold / Inter-Bold / OpenSans-Bold):", font_options)

font_path = None
if selected_font_option == "➕ Unggah Font Baru dari Komputer (Lokal)":
    local_font_file = st.file_uploader("📂 Unggah file font (.ttf / .otf):", type=["ttf", "otf"])
    if local_font_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp_font:
            tmp_font.write(local_font_file.getvalue())
            font_path = tmp_font.name
else:
    if selected_font_option in github_fonts:
        font_path = github_fonts[selected_font_option]

# --- PROSES UNGGAH GAMBAR ---
uploaded_file = st.file_uploader("🖼️ Unggah Tangkapan Layar Bukti Transaksi (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    width, height = image.size
    
    with st.spinner("Menganalisis layout dan mendeteksi ukuran font asli..."):
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

        st.markdown("**2. Pengaturan Nominal Otomatis**")
        selected_index = st.number_input("Pilih Baris Index yang Ingin Diubah:", min_value=0, max_value=len(line_df)-1, value=0, step=1)
        target_row = line_df.iloc[selected_index]
        st.info(f"Baris Terpilih: **'{target_row['text']}'**")
        
        raw_input_text = st.text_input("Nominal Baru (Contoh: 450,000.00):", value="450,000.00")

        if st.button("✨ Eksekusi Auto-Render"):
            # 1. Format Teks Cerdas (Memastikan 'IDR ' di depan)
            clean_number = "".join(c for c in raw_input_text if c.isprintable()).strip()
            if not clean_number.startswith("IDR"):
                final_display_text = f"IDR {clean_number}"
            else:
                final_display_text = clean_number

            edited_image = image.copy()
            draw = ImageDraw.Draw(edited_image)
            
            x = int(target_row['left'])
            y = int(target_row['top'])
            w = int(target_row['width'])
            h = int(target_row['height'])
            
            # 2. Skala Font Otomatis (Menggunakan 90% dari tinggi bounding box asli)
            font_size = max(16, int(h * 0.90))
            
            try:
                font = ImageFont.truetype(font_path, size=font_size) if font_path else ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
                
            # 3. Kalkulasi Bentang Teks Baru
            dummy_draw = ImageDraw.Draw(edited_image)
            try:
                text_bbox = dummy_draw.textbbox((0, 0), final_display_text, font=font)
                new_text_w = text_bbox[2] - text_bbox[0]
            except Exception:
                new_text_w = len(final_display_text) * (font_size * 0.5)
                
            # 4. Kalkulasi Center Alignment Mutlak
            original_center_x = x + (w / 2)
            final_x = int(original_center_x - (new_text_w / 2))
            
            # 5. Pembersihan Area Solid & Bersih (Menimpa area lama tanpa blur)
            clean_width = max(w, int(new_text_w)) + 60
            clean_left = int(original_center_x - (clean_width / 2))
            
            box_coords = (
                max(0, clean_left), 
                max(0, y - 6), 
                min(width, clean_left + clean_width), 
                min(height, y + h + 8)
            )
            
            # Mengambil sampel warna asli (biasanya putih / sangat cerah)
            try:
                sample_color = image.getpixel((max(0, clean_left - 5), y + (h // 2)))
            except Exception:
                sample_color = (255, 255, 255)
                
            draw.rectangle(box_coords, fill=sample_color)
            
            # 6. Render Native Font (Jarak huruf diatur otomatis oleh file font)
            text_color = (13, 37, 63) # Warna biru BCA pekat
            draw.text((final_x, y), final_display_text, fill=text_color, font=font)
            
            st.markdown("**🎯 Hasil Tangkapan Layar Termodifikasi Sempurna**")
            st.image(edited_image, use_container_width=True)
            
            buf = io.BytesIO()
            edited_image.save(buf, format="PNG")
            st.download_button(
                label="📥 Unduh Hasil Manipulasi (PNG)",
                data=buf.getvalue(),
                file_name="bca_auto_perfect.png",
                mime="image/png"
            )
    else:
        st.warning("Tidak ada baris teks yang terdeteksi.")
else:
    st.info("Silakan unggah tangkapan layar bukti transaksi untuk memulai.")
