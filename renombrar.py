import os

# Ruta de la carpeta
ruta = r"C:\Users\74769549\Desktop\Nueva carpeta (5)"

# Extensiones de imagen válidas
extensiones = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")

for archivo in os.listdir(ruta):
    if archivo.lower().endswith(extensiones):
        ruta_completa = os.path.join(ruta, archivo)

        # Evitar renombrar dos veces
        if archivo.startswith("1_") or archivo.startswith("3_"):
            continue

        # Condición según inicio del nombre
        if archivo.startswith("00"):
            nuevo_nombre = "3_" + archivo
        else:
            nuevo_nombre = "1_" + archivo

        nueva_ruta = os.path.join(ruta, nuevo_nombre)

        os.rename(ruta_completa, nueva_ruta)
        print(f"Renombrado: {archivo} -> {nuevo_nombre}")

print("Proceso terminado ✅")