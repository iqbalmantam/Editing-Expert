import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import pandas as pd
import io

st.set_page_config(page_title="Precision Receipt Text Editor", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("**🌐 Precision Digital Receipt Editor**")
st.markdown("Sistem pembersihan blok cerdas dengan pencocokan warna piksel asli dan penataan posisi teks yang presisi.")

uploaded_file = st.file_uploader("Unggah tangkapan layar bukti transaksi (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    img_w, img_h = image.size
    
    with st.spinner("Menganalisis tata letak dan struktur baris..."):
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

        if st.button("✨ Eksekusi Pembersihan & Render Sempurna"):
            edited_image = image.copy()
            draw = ImageDraw.Draw(edited_image)
            
            x = int(target_row['left'])
            y = int(target_row['top'])
            w = int(target_row['width'])
            h = int(target_row['height'])
            
            # Tentukan ukuran font yang proporsional berdasarkan tinggi baris asli
            font_size = max(14, int(h * 0.85))
            
            try:
                font = ImageFont.truetype("font.ttf", size=font_size)
            except Exception:
                try:
                    font = ImageFont.load_default(size=font_size)
                except TypeError:
                    font = ImageFont.load_default()
            
            # Hitung lebar teks baru untuk menentukan area hapus yang pas
            dummy_draw = ImageDraw.Draw(edited_image)
            try:
                text_bbox = dummy_draw.textbbox((0, 0), new_text, font=font)
                new_text_w = text_bbox[2] - text_bbox[0]
            except Exception:
                new_text_w = len(new_text) * (font_size * 0.5)
                
            total_clean_w = max(w, int(new_text_w)) + 20
            
            # Kotak pembersihan latar belakang agar teks lama hilang total tanpa sisa
            box_coords = (
                max(0, x - 5), 
                max(0, y - 4), 
                min(img_w, x + total_clean_w), 
                min(img_h, y + h + 6)
            )
            
            # Sampel warna latar belakang dari sisi kiri teks
            try:
                sample_color = image.getpixel((max(0, x - 5), y + (h // 2)))
            except Exception:
                sample_color = (255, 255, 255)
                
            draw.rectangle(box_coords, fill=sample_color)
            
            # Gunakan warna teks standar perbankan digital (biru gelap pekat)
            text_color = (24, 34, 54)
            
            # Render teks baru secara bersih pada koordinat asal
            draw.text((x, y), new_text, fill=text_color, font=font)
            
            st.markdown("**🎯 Hasil Tangkapan Layar Termodifikasi Sempurna**")
            st.image(edited_image, use_container_width=True)
            
            buf = io.BytesIO()
            edited_image.save(buf, format="PNG")
            st.download_button(
                label="📥 Unduh Hasil Manipulasi (PNG)",
                data=buf.getvalue(),
                file_name="clean_receipt_edited.png",
                mime="image/png"
            )
    else:
        st.warning("Tidak ada baris teks yang terdeteksi.")
else:
    st.info("Silakan unggah tangkapan layar bukti transaksi untuk memulai.")
