import os
import cv2
import numpy as np
from PIL import Image, ImageOps
import streamlit as st
import io
import zipfile
import base64
import re

# =====================
# CONFIGURACIÓN SUNEDU
# =====================
IMG_WIDTH = 240
IMG_HEIGHT = 288
IMG_DPI = 300
MAX_FILESIZE_KB = 50
ALLOWED_EXTS = {".jpg", ".jpeg", ".png"}

# =====================
# FONDO + ESTILO (panel blanco)
# =====================
def set_background_and_style(image_path):
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <style>
        /* Fondo de toda la app */
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-attachment: fixed;
        }}
        /* Hace que TODO el contenido se dibuje sobre un panel blanco */
        .block-container {{
            background: rgba(255,255,255,0.98);
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
            padding: 2rem 2.5rem;
            max-width: 1000px;
        }}
        /* Header transparente para que se vea el fondo */
        header, .stToolbar {{ background: transparent; }}
        /* Texto negro dentro del panel */
        h1, h2, h3, p, label, span {{ color: #000 !important; }}
        /* Botón de descarga con un poco más de presencia */
        .stDownloadButton > button {{
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        @media (max-width: 640px) {{
            .block-container {{ padding: 1.25rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

set_background_and_style("cayetano_central.png")

# =====================
# UTILIDADES IMAGEN
# =====================
def fondo_blanco(img_cv, thr=245, frac_min=0.98):
    h, w = img_cv.shape[:2]
    pads = [
        img_cv[0:10, 0:10],
        img_cv[0:10, w-10:w],
        img_cv[h-10:h, 0:10],
        img_cv[h-10:h, w-10:w],
        img_cv[0:5, :],
        img_cv[h-5:h, :],
        img_cv[:, 0:5],
        img_cv[:, w-5:w],
    ]
    ratios = []
    for p in pads:
        if p.size == 0:
            continue
        gray = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
        ratios.append((gray >= thr).mean())
    return all(r >= frac_min for r in ratios) if ratios else False

def abrir_normalizado(uploaded_file):
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    if img.mode == "RGBA":
        bg = Image.new("RGBA", img.size, (255,255,255,255))
        img = Image.alpha_composite(bg, img).convert("RGB")
    else:
        img = img.convert("RGB")
    return img

def leer_dpi(img: Image.Image):
    dpi = img.info.get("dpi")
    return dpi if isinstance(dpi, tuple) else None

def guardar_jpg(out_img: Image.Image, quality=85):
    bio = io.BytesIO()
    out_img.save(
        bio, "JPEG",
        dpi=(IMG_DPI, IMG_DPI),
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling=2
    )
    bio.seek(0)
    return bio

def extraer_identificador(nombre_archivo: str):
    """
    Extrae DNI (8 dígitos), Carné de extranjería (9 dígitos)
    o Pasaporte (alfanumérico 6-12 caracteres) desde el nombre del archivo.
    Limpia prefijos tipo '1_' y sufijos con nombres.
    """
    base = os.path.splitext(nombre_archivo)[0]  # sin extensión

    # Si hay "-", tomar lo que esté antes (ej: "44428590- SOTO ..." → "44428590")
    if "-" in base:
        base = base.split("-")[0].strip()

    # Si hay "_", tomar lo último (ej: "1_927720733" → "927720733")
    if "_" in base:
        base = base.split("_")[-1].strip()

    # DNI (8 dígitos)
    if re.fullmatch(r"\d{8}", base):
        return base

    # CE (9 dígitos)
    if re.fullmatch(r"\d{9}", base):
        return base

    # Pasaporte (alfanumérico, 6–12 caracteres)
    if re.fullmatch(r"[A-Za-z0-9]{6,12}", base):
        return base.upper()

    return None

# =====================
# VALIDACIÓN
# =====================
def validar_imagen(uploaded_file, identificador):
    errores = []
    avisos = []

    # Extensión/MIME
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTS:
        avisos.append("Formato no JPG/JPEG/PNG: se convertirá a JPG.")

    # Tamaño en KB
    filesize_kb = len(uploaded_file.getbuffer()) / 1024
    if filesize_kb > MAX_FILESIZE_KB:
        avisos.append(f"Pesa {filesize_kb:.1f} KB (> {MAX_FILESIZE_KB}). Se recomprimirá.")

    # Apertura normalizada
    try:
        img = abrir_normalizado(uploaded_file)
    except Exception as e:
        errores.append(f"No se pudo abrir la imagen: {e}")
        return errores, avisos

    # Dimensiones
    if img.size != (IMG_WIDTH, IMG_HEIGHT):
        avisos.append(f"Dimensiones {img.size[0]}x{img.size[1]}: se redimensionará a {IMG_WIDTH}x{IMG_HEIGHT}.")

    # DPI
    dpi = leer_dpi(img)
    if dpi != (IMG_DPI, IMG_DPI):
        avisos.append(f"DPI {dpi}: se fijará a {IMG_DPI}.")

    # Fondo blanco (bordes y esquinas)
    uploaded_file.seek(0)
    img_cv = cv2.imdecode(np.frombuffer(uploaded_file.getbuffer(), np.uint8), cv2.IMREAD_COLOR)
    if img_cv is None or not fondo_blanco(img_cv):
        avisos.append("Fondo no suficientemente blanco: se normalizará.")

    # Identificador en nombre
    if not identificador:
        errores.append("El nombre del archivo no contiene un identificador válido (DNI/CE/Pasaporte).")

    return errores, avisos

# =====================
# CORRECCIÓN
# =====================
def corregir_imagen(uploaded_file):
    img = abrir_normalizado(uploaded_file)
    img = img.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)

    # Componer en lienzo blanco (garantiza fondo blanco)
    canvas = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255))
    canvas.paste(img, (0, 0))

    quality = 85
    bio = guardar_jpg(canvas, quality=quality)

    while bio.getbuffer().nbytes > MAX_FILESIZE_KB * 1024 and quality > 25:
        quality -= 10
        bio = guardar_jpg(canvas, quality=quality)

    return bio, quality

# =====================
# UI
# =====================
st.markdown("<h1 style='color:#910007;'>📸 Validador y Corrector de Fotos SUNEDU</h1>", unsafe_allow_html=True)
st.markdown("<p>Sube las fotos de los estudiantes para validar y corregir según los criterios SUNEDU.</p>", unsafe_allow_html=True)
st.markdown("<p style='font-weight:bold; color:#910007;'>Subir fotos de estudiantes</p>", unsafe_allow_html=True)

uploaded_files = st.file_uploader("", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

fotos_corregidas = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        identificador = extraer_identificador(uploaded_file.name) or ""
        titulo = f"📌 ID: {identificador}" if identificador else f"📌 Archivo: {uploaded_file.name}"
        st.markdown(f"<h3>{titulo}</h3>", unsafe_allow_html=True)

        img_original = abrir_normalizado(uploaded_file)
        st.image(img_original, caption=f"Foto subida: {uploaded_file.name}", width=220)

        errores, avisos = validar_imagen(uploaded_file, identificador)

        if errores:
            st.error("⛔ Problemas críticos:")
            for e in errores:
                st.write("-", e)

        if avisos:
            st.warning("🛠 Se aplicarán correcciones:")
            for a in avisos:
                st.write("-", a)

        with st.spinner("Corrigiendo..."):
            bio, used_quality = corregir_imagen(uploaded_file)

        size_kb = bio.getbuffer().nbytes / 1024
        if size_kb > MAX_FILESIZE_KB:
            st.warning(f"Quedó en {size_kb:.1f} KB (> {MAX_FILESIZE_KB}). Se mantuvo la mejor calidad posible (q={used_quality}).")
        else:
            st.success("✅ Imagen corregida y dentro de los límites.")

        st.image(bio, caption=f"Foto corregida: {(identificador or 'SIN_ID')}.jpg", width=220)
        fotos_corregidas.append((f"{(identificador or 'SIN_ID')}.jpg", bio.getvalue()))

    if fotos_corregidas:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for nombre, data in fotos_corregidas:
                zipf.writestr(nombre, data)
        zip_buffer.seek(0)
        st.download_button(
            "📦 Descargar fotos corregidas (ZIP)",
            data=zip_buffer,
            file_name="fotos_corregidas.zip",
            mime="application/zip"
        )
