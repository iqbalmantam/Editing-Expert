import streamlit as st
from PIL import Image, ImageDraw
import pytesseract
import pandas as pd
import io

st.set_page_config(page_title="Pixel-Perfect Glyph Stitching Editor", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("**🌐 Pixel-Perfect Glyph Stitching & Character Cloning Editor**")
st.markdown("Sistem kloning piksel tingkat lanjut yang merakit ulang karakter asli dari gambar untuk hasil editan yang 100% identik.")

uploaded_file = st.file_uploader("Unggah tangkapan layar bukti transaksi (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    img_w, img_h = image.size
    
    with st.spinner("Mengekstrak dan memetakan karakter piksel asli..."):
        # 1. Ekstraksi Kotak Karakter Individual (Glyph Extraction)
        boxes_data = pytesseract.image_to_boxes(image)
        glyph_dict = {}
        
        for line in boxes_data.splitlines():
            parts = line.split()
            if len(parts) == 6:
                char, xmin, ymin, xmax, ymax, _ = parts
                xmin, ymin, xmax, ymax = int(xmin), int(ymin), int(xmax), int(ymax)
                
                # Konversi koordinat Tesseract (bottom-left origin) ke PIL (top-left origin)
                pil_box = (xmin, img_h - ymax, xmax, img_h -ymin)
                
                # Pastikan koordinat valid dan crop karakter
                if pil_box[2] > pil_box[0] and pil_box[3] > pil_box[1]:
                    char_crop = image.crop(pil_box)
                    # Simpan glyph terbaik (prioritaskan jika belum ada)
                    if char not in glyph_dict:
                        glyph_dict[char] = char_crop

        # 2. Deteksi Baris Teks untuk Pemilihan Target
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

        st.markdown("**2. Masukkan Teks Baru untuk Dirakit Otomatis**")
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

        if st.button("✨ Eksekusi Kloning Karakter Sempurna"):
            edited_image = image.copy()
            draw = ImageDraw.Draw(edited_image)
            
            x = int(target_row['left'])
            y = int(target_row['top'])
            w = int(target_row['width'])
            h = int(target_row['height'])
            
            # Perhitungan area pembersihan latar belakang agar teks lama lenyap total
            box_coords = (
                max(0, x - 10), 
                max(0, y - 4), 
                min(img_w, x + w + 25), 
                min(img_h, y + h + 6)
            )
            
            try:
                sample_color = image.getpixel((max(0, x - 5), y + (h // 2)))
            except Exception:
                sample_color = (255, 255, 255)
                
            draw.rectangle(box_coords, fill=sample_color)
            
            # 3. Proses Perakitan Glyph (Stitching Matrix)
            current_x = x
            stitching_success = True
            
            for char in new_text:
                if char in glyph_dict:
                    glyph_img = glyph_dict[char]
                    # Tempelkan potongan karakter asli ke posisi target
                    edited_image.paste(glyph_img, (current_x, y), glyph_img.convert("RGBA"))
                    current_x += glyph_img.width
                elif char == " ":
                    current_x += 10  # Spasi manual jika karakter spasi
                else:
                    stitching_success = False
                    break
            
            # Fallback jika ada karakter yang tidak memiliki sampel glyph di gambar
            if not stitching_success or current_x == x:
                st.warning("⚠️ Sebagian karakter baru tidak ditemukan sampelnya di gambar ini. Menggunakan render teks standar.")
                from PIL import ImageFont
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None
                draw.text((x, y), new_text, fill=(24, 34, 54), font=font)

            st.markdown("**🎯 Hasil Tangkapan Layar Termodifikasi Sempurna**")
            st.image(edited_image, use_container_width=True)
            
            buf = io.BytesIO()
            edited_image.save(buf, format="PNG")
            st.download_button(
                label="📥 Unduh Hasil Manipulasi (PNG)",
                data=buf.getvalue(),
                file_name="glyph_stitched_receipt.png",
                mime="image/png"
            )
    else:
        st.warning("Tidak ada baris teks yang terdeteksi.")
else:
    st.info("Silakan unggah tangkapan layar bukti transaksi untuk memulai.")
