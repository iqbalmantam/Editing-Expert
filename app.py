import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pytesseract
import pandas as pd
import os
import io

st.set_page_config(page_title="BCA Ultimate Supersampling Editor", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("**🌐 BCA Ultimate Supersampling Receipt Editor**")
st.markdown("Menggunakan teknik render teks resolusi 4x lipat (LANCZOS Anti-Aliasing) untuk hasil tepian huruf yang sangat halus dan realistis.")

# --- MANAJEMEN FONT EKSKLUSIF GITHUB ---
# Sistem dioptimalkan untuk beroperasi sepenuhnya dari direktori repositori
FONT_DIR = "fonts"
github_fonts = {}
if os.path.exists(FONT_DIR) and os.path.isdir(FONT_DIR):
    for root, dirs, files in os.walk(FONT_DIR):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".otf"):
                full_path = os.path.join(root, file)
                display_name = os.path.relpath(full_path, FONT_DIR)
                github_fonts[display_name] = full_path

if not github_fonts:
    st.error("⚠️ Folder 'fonts' kosong atau tidak ditemukan. Harap pastikan file font sudah didorong (push) ke repositori.")
    st.stop()

sorted_font_names = sorted(github_fonts.keys(), key=lambda name: ("italic" in name.lower(), name))
selected_font_option = st.selectbox("Pilih Jenis Font (Pastikan menggunakan varian Bold):", sorted_font_names)
font_path = github_fonts[selected_font_option]

# --- PROSES UNGGAH GAMBAR ---
uploaded_file = st.file_uploader("🖼️ Unggah Tangkapan Layar Bukti Transaksi (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    width, height = image.size
    
    with st.spinner("Menganalisis matriks piksel..."):
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

        st.markdown("**2. Pengaturan Nominal Cerdas**")
        selected_index = st.number_input("Pilih Baris Index yang Ingin Diubah:", min_value=0, max_value=len(line_df)-1, value=0, step=1)
        target_row = line_df.iloc[selected_index]
        st.info(f"Baris Terpilih: **'{target_row['text']}'**")
        
        raw_input_text = st.text_input("Nominal Baru (Contoh: 450,000.00):", value="450,000.00")

        if st.button("✨ Eksekusi Supersampling Render"):
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
            
            font_size = max(16, int(h * 0.90))
            
            # --- TAHAP 1: PEMERATAAN LATAR BELAKANG ---
            dummy_font = ImageFont.truetype(font_path, size=font_size)
            dummy_draw = ImageDraw.Draw(edited_image)
            new_text_w = dummy_draw.textbbox((0, 0), final_display_text, font=dummy_font)[2]
                
            original_center_x = x + (w / 2)
            final_x = int(original_center_x - (new_text_w / 2))
            
            clean_width = max(w, int(new_text_w)) + 50
            clean_left = int(original_center_x - (clean_width / 2))
            
            box_coords = (
                max(0, clean_left), 
                max(0, y - 6), 
                min(width, clean_left + clean_width), 
                min(height, y + h + 8)
            )
            
            try:
                sample_color = image.getpixel((max(0, clean_left - 5), y + (h // 2)))
            except Exception:
                sample_color = (255, 255, 255)
                
            # Gunakan feathering buatan pada kotak agar tidak terlalu kaku
            draw.rectangle(box_coords, fill=sample_color)
            
            # --- TAHAP 2: SUPERSAMPLING TEXT RENDERING ---
            scale_factor = 4 # Skala 400% untuk anti-aliasing sempurna
            super_font_size = font_size * scale_factor
            super_font = ImageFont.truetype(font_path, size=super_font_size)
            
            # Buat kanvas transparan berukuran 4x lipat dari gambar asli
            text_canvas = Image.new("RGBA", (width * scale_factor, height * scale_factor), (255, 255, 255, 0))
            text_draw = ImageDraw.Draw(text_canvas)
            
            # Render teks di kanvas raksasa
            text_color = (13, 37, 63, 255) # RGBA Blue BCA
            super_x = final_x * scale_factor
            super_y = y * scale_factor
            
            text_draw.text((super_x, super_y), final_display_text, fill=text_color, font=super_font)
            
            # Susutkan (Downscale) kanvas menggunakan algoritma LANCZOS
            # Ini menciptakan efek anti-aliasing mikroskopis yang identik dengan mesin render HP
            text_canvas_resized = text_canvas.resize((width, height), Image.Resampling.LANCZOS)
            
            # Tempel teks halus ke gambar utama
            edited_image.paste(text_canvas_resized, (0, 0), text_canvas_resized)
            
            st.markdown("**🎯 Hasil Tangkapan Layar Termodifikasi Sempurna (Supersampled)**")
            st.image(edited_image, use_container_width=True)
            
            buf = io.BytesIO()
            edited_image.save(buf, format="PNG")
            st.download_button(
                label="📥 Unduh Hasil Manipulasi (PNG)",
                data=buf.getvalue(),
                file_name="bca_supersampled.png",
                mime="image/png"
            )
    else:
        st.warning("Tidak ada baris teks yang terdeteksi.")
else:
    st.info("Silakan unggah tangkapan layar bukti transaksi untuk memulai.")
