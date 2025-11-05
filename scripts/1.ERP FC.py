import pdfplumber
import pandas as pd
import os
import re
from datetime import datetime
import sys

# ======================================
# 🔧 CONFIGURACIÓN GENERAL (COMPATIBLE CON FLASK Y RENDER)
# ======================================
BASE_FOLDER = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get("UPLOAD_FOLDER", "/tmp/uploads/1_ERP_FC")
)
os.makedirs(BASE_FOLDER, exist_ok=True)
print(f"📂 Carpeta activa: {BASE_FOLDER}")

# ======================================
# 🧹 LIMPIEZA DE NOMBRES DE ARCHIVOS
# ======================================
def limpiar_nombre_archivo(nombre):
    caracteres_no_validos = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in caracteres_no_validos:
        nombre = nombre.replace(char, '-')
    return nombre[:200]

# ======================================
# 🧾 PROCESADOR PRINCIPAL DE FACTURAS ERP
# ======================================
def extraer_proveedores_subtotales(pdf_folder, output_excel):
    datos = []

    for file in os.listdir(pdf_folder):
        if not file.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_folder, file)
        factura = os.path.splitext(file)[0]
        proveedor = "No encontrado"
        subtotal = None
        fecha_formateada = "No encontrada"

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue

                    # ======= Extraer proveedor =======
                    match_prov = re.search(r"proveedo[r|ra]?\s*:?(.+?)(?=\n|por concepto|total|$)", text, re.IGNORECASE)
                    if match_prov:
                        proveedor = match_prov.group(1).strip()

                    # ======= Extraer subtotal =======
                    match_sub = re.search(r"subtotal\s*[:\s]*([\d\.,]+)", text.lower())
                    if match_sub:
                        valor = match_sub.group(1).replace(".", "").replace(",", "")
                        subtotal = int(valor) if valor.isdigit() else None

                    # ======= Extraer fecha =======
                    match_fecha = re.search(r"(\d{1,2})\s*de\s*(\w+)\s*de\s*(\d{4})", text.lower())
                    if match_fecha:
                        dia, mes_texto, anio = match_fecha.groups()
                        meses = {
                            "enero": "1", "febrero": "2", "marzo": "3", "abril": "4",
                            "mayo": "5", "junio": "6", "julio": "7", "agosto": "8",
                            "septiembre": "9", "octubre": "10", "noviembre": "11", "diciembre": "12"
                        }
                        mes = meses.get(mes_texto, "0")
                        fecha_formateada = f"{int(dia)}/{int(mes)}/{anio}"

        except Exception as e:
            print(f"❌ Error procesando {file}: {e}")
            continue

        # ======= Nuevo nombre =======
        nuevo_nombre = limpiar_nombre_archivo(f"{factura}_{fecha_formateada}_{proveedor}_{subtotal or 0}.pdf")
        nuevo_path = os.path.join(pdf_folder, nuevo_nombre)
        try:
            os.rename(pdf_path, nuevo_path)
        except Exception:
            print(f"⚠️ No se pudo renombrar: {file}")

        datos.append([factura, fecha_formateada, proveedor, subtotal, nuevo_nombre])

    # ======= Guardar resultados =======
    df = pd.DataFrame(datos, columns=["Factura", "Fecha", "Proveedor", "Subtotal", "Archivo Renombrado"])
    output_path = os.path.join(pdf_folder, output_excel)
    df.to_excel(output_path, index=False)

    print(f"✅ Excel generado: {output_path}")
    return output_path

# ======================================
# 🚀 EJECUCIÓN PRINCIPAL
# ======================================
if __name__ == "__main__":
    pdf_folder = BASE_FOLDER
    output_excel = "ERP_Facturas_Resultados.xlsx"
    resultado = extraer_proveedores_subtotales(pdf_folder, output_excel)

    # Solo abrir carpeta si está en entorno local
    if os.name == "nt":
        os.startfile(os.path.dirname(resultado))

