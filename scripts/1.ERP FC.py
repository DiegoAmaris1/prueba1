import pdfplumber
import pandas as pd
import os
import re
from datetime import datetime
import sys

# ======================================
# 🔧 CONFIGURACIÓN GENERAL (COMPATIBLE CON FLASK, LOCAL Y RENDER)
# ======================================

# 🔥 PRIORIDAD 1: Si se pasa como argumento (desde Flask)
if len(sys.argv) > 1:
    BASE_FOLDER = sys.argv[1]
    print(f"✅ Carpeta recibida por argumento: {BASE_FOLDER}")
# 🔥 PRIORIDAD 2: Si existe variable de entorno (Render standalone)
elif os.environ.get("UPLOAD_FOLDER"):
    BASE_FOLDER = os.environ["UPLOAD_FOLDER"]
    print(f"✅ Carpeta desde variable de entorno: {BASE_FOLDER}")
# 🔥 PRIORIDAD 3: Modo local (Windows)
else:
    BASE_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "uploads", "1_ERP_FC")
    print(f"✅ Modo local - Carpeta: {BASE_FOLDER}")

os.makedirs(BASE_FOLDER, exist_ok=True)
print(f"📂 Carpeta activa: {BASE_FOLDER}")

# Verificar si hay archivos PDF
pdf_files = [f for f in os.listdir(BASE_FOLDER) if f.lower().endswith('.pdf')]
print(f"📄 Archivos PDF encontrados: {len(pdf_files)}")
if pdf_files:
    print(f"   Archivos: {', '.join(pdf_files[:5])}{'...' if len(pdf_files) > 5 else ''}")

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
    archivos_procesados = 0
    archivos_con_error = 0

    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    total_archivos = len(pdf_files)
    
    print(f"\n🔄 Iniciando procesamiento de {total_archivos} archivos PDF...")

    for idx, file in enumerate(pdf_files, 1):
        pdf_path = os.path.join(pdf_folder, file)
        factura = os.path.splitext(file)[0]
        proveedor = "No encontrado"
        subtotal = None
        fecha_formateada = "No encontrada"

        print(f"📄 [{idx}/{total_archivos}] Procesando: {file}")

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

            archivos_procesados += 1
            print(f"   ✅ Extraído - Proveedor: {proveedor[:30]}, Subtotal: {subtotal}, Fecha: {fecha_formateada}")

        except Exception as e:
            archivos_con_error += 1
            print(f"   ❌ Error procesando {file}: {e}")
            continue

        # ======= Nuevo nombre =======
        nuevo_nombre = limpiar_nombre_archivo(f"{factura}_{fecha_formateada}_{proveedor}_{subtotal or 0}.pdf")
        nuevo_path = os.path.join(pdf_folder, nuevo_nombre)
        
        try:
            if pdf_path != nuevo_path:  # Solo renombrar si el nombre cambió
                os.rename(pdf_path, nuevo_path)
                print(f"   📝 Renombrado a: {nuevo_nombre[:50]}...")
        except Exception as e:
            print(f"   ⚠️ No se pudo renombrar: {e}")

        datos.append([factura, fecha_formateada, proveedor, subtotal, nuevo_nombre])

    # ======= Guardar resultados =======
    df = pd.DataFrame(datos, columns=["Factura", "Fecha", "Proveedor", "Subtotal", "Archivo Renombrado"])
    output_path = os.path.join(pdf_folder, output_excel)
    df.to_excel(output_path, index=False)

    print(f"\n📊 RESUMEN DEL PROCESAMIENTO:")
    print(f"   ✅ Archivos procesados exitosamente: {archivos_procesados}")
    print(f"   ❌ Archivos con error: {archivos_con_error}")
    print(f"   📁 Excel generado: {output_path}")
    print(f"   📂 Ubicación: {pdf_folder}")

    return output_path

# ======================================
# 🚀 EJECUCIÓN PRINCIPAL
# ======================================
if __name__ == "__main__":
    pdf_folder = BASE_FOLDER
    output_excel = "ERP_Facturas_Resultados.xlsx"
    
    try:
        resultado = extraer_proveedores_subtotales(pdf_folder, output_excel)
        print(f"\n🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
        print(f"📥 Archivo de resultados: {resultado}")
        
        # Solo abrir carpeta si está en entorno local Windows
        if os.name == "nt":
            try:
                os.startfile(os.path.dirname(resultado))
            except:
                pass
                
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)