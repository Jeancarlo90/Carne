import os
import cv2
import numpy as np
from PIL import Image, ImageOps
import streamlit as st
import io
import zipfile
import base64

# =====================
# CONFIGURACIÓN SUNEDU
# =====================
IMG_WIDTH = 240
IMG_HEIGHT = 288
IMG_DPI = 300
MAX_FILESIZE_KB = 50
ALLOWED_EXT = ".jpg"

# =====================
# CONFIGURAR FONDO + ESTILOS
# =====================
def set_background_and_style(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()

    st.markdown(
        f"""
        <style>
        /* Fondo completo */
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-attachment: fixed;
        }}

        /* Contenedor central blanco translúcido */
        .main-box {{
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 18px;
            padding: 30px 40px;
            margin: 50px auto;
            max-width: 950px;
            box-shadow: 0px 8px 24px rgba(0,0,0,0.25);
        }}

        /* Alinear todo dentro del cuadro */
        .stMarkdown, .stText, .stImage, .stFileUploader, .stDownloadButton {{
            color: #000000;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Fondo con tu imagen
set_background_and_style("cayetano_central.png")

# =====================
# FUNCIONES DE VALIDACIÓN
# =====================
def validar_imagen(path, dni):
    errores = []
    try:
        # Validar extensión
        ext = os.path.splitext(path.name)[1].lower()
        if ext != ALLOWED_EXT:
            errores.append("❌ La imagen debe estar en formato JPG (.jpg).")

        # Validar tamaño del archivo
        filesize_kb = len(path.getbuffer()) / 1024
        if filesize_kb > MAX_FILESIZE_KB:
            errores.append(f"❌ La imagen supera los {MAX_FILESIZE_KB} KB ({filesize_kb:.1f} KB).")

        # Validar dimensiones
        img = Image.open(path)
        if img.size != (IMG_WIDTH, IMG_HEIGHT):
            errores.append(f"❌ La imagen debe tener dimensiones exactas de {IMG_WIDTH}x{IMG_HEIGHT}px. (Tiene {img.size[0]}x{img.size[1]}px).")

        # Validar fondo blanco
        img_cv = cv2.imdecode(np.frombuffer(path.getbuffer(), np.uint8), cv2.IMREAD_COLOR)
        if img_cv is not None:
            h, w = img_cv.shape[:2]
            y1, y2 = min(5, h-1), min(20, h)
            x1, x2 = min(5, w-1), min(20, w)
            corner = img_cv[y1:y2, x1:x2]
            if corner.size > 0:
                mean_color = corner.mean(axis=(0, 1))
                if not (mean_color > 240).all():
                    errores.append("❌ El fondo no es blanco absoluto.")
        else:
            errores.append("⚠️ No se pudo analizar la imagen con OpenCV.")

        # Validar nombre del archivo
        filename = os.path.splitext(path.name)[0]
        if not (filename.isdigit() and len(filename) == 8):
            errores.append("❌ El nombre del archivo debe ser exactamente 8 dígitos (ej. 41803077.jpg).")

    except Exception as e:
        errores.append(f"⚠️ Error procesando la imagen: {e}")
    return errores

def corregir_imagen(path, dni):
    img = Image.open(path).convert("RGB")
    img = ImageOps.exif_transpose(img)
    img = img.resize((IMG_WIDTH, IMG_HEIGHT))
    new_img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255))
    new_img.paste(img, (0, 0))

    output = io.BytesIO()
    new_img.save(output, "JPEG", dpi=(IMG_DPI, IMG_DPI), quality=85, optimize=True)

    quality = 85
    while output.getbuffer().nbytes > MAX_FILESIZE_KB * 1024 and quality > 20:
        quality -= 15
        output = io.BytesIO()
        new_img.save(output, "JPEG", dpi=(IMG_DPI, IMG_DPI), quality=quality, optimize=True)

    output.seek(0)
    return output

# =====================
# STREAMLIT APP
# =====================
st.markdown("<div class='main-box'>", unsafe_allow_html=True)

st.markdown("<h1 style='color:#910007;'>📸 Validador y Corrector de Fotos SUNEDU</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#000000;'>Sube las fotos de los estudiantes para validar y corregir según los criterios SUNEDU.</p>", unsafe_allow_html=True)
st.markdown("<p style='color:#000000; font-weight:bold;'>Subir fotos de estudiantes</p>", unsafe_allow_html=True)

uploaded_files = st.file_uploader("", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

fotos_corregidas = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        dni = os.path.splitext(uploaded_file.name)[0]
        st.markdown(f"<h3 style='color:#000000;'>📌 DNI: {dni}</h3>", unsafe_allow_html=True)

        img_original = Image.open(uploaded_file).convert("RGB")
        img_original = ImageOps.exif_transpose(img_original)
        st.image(img_original, caption=f"Foto subida: {uploaded_file.name}", width=200)

        errores = validar_imagen(uploaded_file, dni)

        if errores:
            st.markdown("<p style='color:#000000;'>⚠️ Errores encontrados:</p>", unsafe_allow_html=True)
            for err in errores:
                st.markdown(f"<p style='color:#000000;'>{err}</p>", unsafe_allow_html=True)

            st.markdown("<p style='color:#000000;'>⚠️ Corrigiendo...</p>", unsafe_allow_html=True)
            corrected_img = corregir_imagen(uploaded_file, dni)
            st.markdown("<p style='color:#000000;'>✅ Imagen corregida</p>", unsafe_allow_html=True)
            st.image(corrected_img, caption=f"Foto corregida: {dni}.jpg", width=200)
            fotos_corregidas.append((f"{dni}.jpg", corrected_img.getvalue()))
        else:
            st.markdown("<p style='color:#000000;'>✅ La imagen cumple con los requisitos SUNEDU.</p>", unsafe_allow_html=True)
            buffer = io.BytesIO()
            uploaded_file.seek(0)
            buffer.write(uploaded_file.read())
            buffer.seek(0)
            fotos_corregidas.append((f"{dni}.jpg", buffer.getvalue()))

    if fotos_corregidas:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for nombre, data in fotos_corregidas:
                zipf.writestr(nombre, data)
        zip_buffer.seek(0)
        st.download_button("📦 Descargar fotos corregidas (ZIP)", data=zip_buffer, file_name="fotos_corregidas.zip", mime="application/zip")

st.markdown("</div>", unsafe_allow_html=True)
