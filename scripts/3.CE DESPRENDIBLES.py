import os
import re
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import pandas as pd
import time

# Carpeta base dinámica (se adapta a local o nube)
BASE_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp")

# Subcarpeta para los documentos bancarios
carpeta_pdfs = os.path.join(BASE_FOLDER, "BANCO_DESPRENDIBLES")
os.makedirs(carpeta_pdfs, exist_ok=True)

# Archivo Excel de salida dentro del mismo entorno
ruta_salida_excel = os.path.join(BASE_FOLDER, "Bancos_Pagos_CE.xlsx")

print(f"📂 Carpeta de PDFs: {carpeta_pdfs}")
print(f"📊 Archivo de salida: {ruta_salida_excel}")

# Configuración OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Diccionario meses (formato OCR)
meses = {
    'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
}

# Regex comunes
fecha_regex = re.compile(r"\d{4}/\d{2}/\d{2}")
valor_regex = re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
beneficiario_regex = re.compile(r"Identificación\s+([A-Za-zÁÉÍÓÚáéíóúÑñ ]+)")

# Lista para guardar los resultados
datos = []

# Recorremos los archivos PDF
for archivo in os.listdir(carpeta_pdfs):
    if not archivo.lower().endswith(".pdf"):
        continue

    ruta_pdf = os.path.join(carpeta_pdfs, archivo)
    fecha_pago = "No encontrado"
    beneficiario = "No encontrado"
    valor_pagar = 0.0

    try:
        doc = fitz.open(ruta_pdf)
        texto = doc[0].get_text().replace('\n', ' ')
        
        # Caso 1: PDF con texto estructurado
        if len(texto) > 200:
            fecha_match = fecha_regex.search(texto)
            valores_match = valor_regex.findall(texto)
            beneficiario_match = beneficiario_regex.search(texto)

            if fecha_match:
                partes = fecha_match.group(0).split("/")
                if len(partes) == 3:
                    fecha_pago = f"{partes[2]}/{partes[1]}/{partes[0]}"
                else:
                    fecha_pago = fecha_match.group(0)
            else:
                fecha_pago = "No encontrado"

            valores_numericos = [float(v.replace(",", "").replace("$", "")) for v in valores_match]
            valor_pagar = sum(valores_numericos) if valores_numericos else 0.00

            if "DIAN - PSE - AÑO:" in texto:
                beneficiario = "DIAN - PSE - AÑO: 2025 PERIODO: 1"
            else:
                beneficiario = beneficiario_match.group(1).strip() if beneficiario_match else "No encontrado"
                beneficiario = re.sub(r"Beneficiario.*", "", beneficiario).strip()

        else:
            # Caso 2: PDF con imagen (OCR)
            pix = doc[0].get_pixmap(dpi=300)
            img_path = "temp.png"
            pix.save(img_path)

            imagen = Image.open(img_path)
            ocr_lineas = pytesseract.image_to_string(imagen, lang='spa').split('\n')
            ocr_lineas = [linea.strip() for linea in ocr_lineas if linea.strip()]
            os.remove(img_path)

            valor_detectado = "0"

            for i, linea in enumerate(ocr_lineas):
                if "comprobante" in linea.lower():
                    for j in range(i+1, min(i+5, len(ocr_lineas))):
                        match = re.search(r"(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\s+(\d{4})", ocr_lineas[j].lower())
                        if match:
                            dia, mes_texto, anio = match.groups()
                            mes_num = meses[mes_texto]
                            fecha_pago = f"{dia.zfill(2)}/{mes_num}/{anio}"
                            break

                if "transferencia" in linea.lower():
                    for j in range(i+1, min(i+5, len(ocr_lineas))):
                        if "$" in ocr_lineas[j] or any(char.isdigit() for char in ocr_lineas[j]):
                            valor_detectado = ocr_lineas[j].replace("$", "").replace(".", "").replace(",", "").strip()
                            break

                if "referencia" in linea.lower() and i + 1 < len(ocr_lineas):
                    beneficiario = ocr_lineas[i+1].strip()

            try:
                valor_pagar = float(valor_detectado)
            except:
                valor_pagar = 0.0

        # Agregar resultado
        datos.append({
            "Fecha de Pago": fecha_pago,
            "Beneficiario": beneficiario,
            "Valor a Pagar": valor_pagar,
            "Nombre Archivo": archivo
        })

    except Exception as e:
        print(f"⚠️ Error procesando {archivo}: {e}")
        continue

# Guardar Excel en la ruta definitiva con nombre correcto
df = pd.DataFrame(datos)
df.to_excel(ruta_salida_excel, index=False)

print(f"\n✅ Proceso completado. Archivo guardado como:\n{ruta_salida_excel}")


print("Esperando 0.1 minuto antes de continuar...") 
time.sleep(3)


import os
import pandas as pd

# Rutas
ruta_excel = os.path.join(user_profile, r"OneDrive\2 PROYECTOS TECNOLOGIA\2 AUTOMAIZACION TECNOLOGIA\2.RESULTADOS\1.DIGITALIZACION\Bancos_Pagos_CE.xlsx")
carpeta_documentos = os.path.join(user_profile, r"OneDrive\2 PROYECTOS TECNOLOGIA\2 AUTOMAIZACION TECNOLOGIA\2.RESULTADOS\1.DIGITALIZACION\2.1 BANCO DESPRENDIBLES")

# Función para limpiar nombres eliminando caracteres no permitidos en archivos
def limpiar_nombre(nombre):
    caracteres_invalidos = r'<>:"/\\|?*'
    for c in caracteres_invalidos:
        nombre = nombre.replace(c, "")
    return nombre.strip()

# Cargar el archivo Excel en un DataFrame
df = pd.read_excel(ruta_excel)

# Verificar que el archivo tiene al menos 4 columnas
if df.shape[1] < 4:
    print("❌ El archivo Excel no tiene suficientes columnas.")
else:
    nombres_archivos = {}
    
    for _, fila in df.iterrows():
        fecha = str(fila[0]).strip().replace("/", "-")  # Reemplazar / con - en la fecha
        razon_social = limpiar_nombre(str(fila[1]))  # Limpiar razón social
        subtotal = str(fila[2]).strip()  # Subtotal
        nombre_archivo = str(fila[3]).strip()  # Nombre de archivo original en Excel

        if nombre_archivo and nombre_archivo.lower().endswith(".pdf"):  # Verificar que sea un PDF
            nuevo_nombre = f"{fecha} - {razon_social} - {subtotal}.pdf"
            nombres_archivos[nombre_archivo] = os.path.join(carpeta_documentos, nuevo_nombre)
    
    # Recorrer los archivos en la carpeta y renombrarlos
    for archivo in os.listdir(carpeta_documentos):
        if archivo.lower().endswith(".pdf"):  
            ruta_original = os.path.join(carpeta_documentos, archivo)

            if archivo in nombres_archivos:
                ruta_nueva = nombres_archivos[archivo]

                # Verificar si el archivo ya tiene el nombre correcto
                if os.path.exists(ruta_nueva):
                    print(f"✅ El archivo ya tiene el nombre correcto: {ruta_nueva}")
                    continue

                # Renombrar el archivo
                try:
                    os.rename(ruta_original, ruta_nueva)
                    print(f"✅ Archivo renombrado: {ruta_nueva}")
                except Exception as e:
                    print(f"❌ No se pudo renombrar {archivo}: {str(e)}")

    print("🔄 Proceso completado.")

os.startfile(carpeta_documentos)

