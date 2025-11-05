import os
import pdfplumber
import pandas as pd
import re
from datetime import datetime
import locale
# Carpeta base dinámica (válida para local y Render)
BASE_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp")

# Crear subcarpeta específica para los comprobantes de egreso
pdf_folder = os.path.join(BASE_FOLDER, "ERP_COMPROBANTE_EGRESO")
os.makedirs(pdf_folder, exist_ok=True)

# Definir la ruta de salida del archivo Excel dentro del mismo entorno
output_excel = os.path.join(BASE_FOLDER, "ERP_Comprobante_Egreso.xlsx")

# Mostrar rutas para depuración
print(f"📂 Carpeta de PDFs: {pdf_folder}")
print(f"📊 Archivo Excel de salida: {output_excel}")

# Establecer el idioma español para reconocer los meses
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')  # Linux/macOS
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain')  # Windows
    except:
        print("⚠️ No se pudo establecer el idioma español. La lectura de fechas podría fallar.")

# 🔧 FUNCION PARA FORMATEAR LA FECHA (ej: 31-03-2025)
def formatear_fecha(fecha_texto):
    try:
        # Buscar la parte que contiene la fecha en español
        match = re.search(r"\d{1,2} de \w+ de \d{4}", fecha_texto.lower())
        if match:
            fecha_extraida = match.group(0)
            fecha_dt = datetime.strptime(fecha_extraida, "%d de %B de %Y")
            return fecha_dt.strftime("%d-%m-%Y")
        else:
            return "Formato inválido"
    except Exception as e:
        print(f"⚠️ No se pudo convertir la fecha: '{fecha_texto}' -> {e}")
        return "Formato inválido"

# 🔧 FUNCION PRINCIPAL
def extraer_totales(pdf_folder, output_excel):
    datos = []
    
    for file in os.listdir(pdf_folder):
        if file.endswith(".pdf"):
            pdf_path = os.path.join(pdf_folder, file)
            factura = file
            factura_sin_extension = file.replace(".pdf", "")
            beneficiario = "No encontrado"
            total_documento = None
            fecha_documento = "No encontrada"
            
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        lineas = text.split("\n")

                        # 📌 Buscar beneficiario
                        for i, linea in enumerate(lineas):
                            if "BENEFICIARIO" in linea and i + 1 < len(lineas):
                                beneficiario = lineas[i + 1].strip()
                                break
                        
                        # 📌 Buscar fecha del documento
                        for i, linea in enumerate(lineas):
                            if "FECHA DOCUMENTO" in linea and i + 1 < len(lineas):
                                fecha_cruda = lineas[i + 1].strip()
                                print(f"🕒 Fecha encontrada: {fecha_cruda}")
                                fecha_documento = formatear_fecha(fecha_cruda)
                                break
                        
                        # 📌 Buscar total del documento
                        total_encontrado = False
                        for i, linea in enumerate(lineas):
                            if "TOTAL DEL DOCUMENTO" in linea and i + 1 < len(lineas):
                                valores = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?", lineas[i + 1])
                                if valores:
                                    total_documento = float(valores[0].replace(".", "").replace(",", "."))  # Convertir a float
                                    total_encontrado = True
                                    break
                        if not total_encontrado:
                            valores = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?", text)
                            if valores:
                                total_documento = float(valores[-1].replace(".", "").replace(",", "."))  # Convertir a float

            # Agregar a la tabla
            datos.append([factura, factura_sin_extension, fecha_documento, beneficiario, total_documento])
    
    # 📤 Crear DataFrame
    df = pd.DataFrame(datos, columns=["Nombre Archivo", "Factura","Fecha Documento" ,"Beneficiario", "Total"])
    
    # 📁 Guardar en Excel
    output_path = os.path.join(output_excel, "ERP_Com_Egreso.xlsx")
    df.to_excel(output_path, index=False)
    print(f"\n✅ Archivo guardado exitosamente en:\n{output_path}")

# Ejecutar la extracción de datos
extraer_totales(pdf_folder, output_excel)

# Parte del código para renombrar los PDFs
def renombrar_pdfs(excel_path, pdf_folder):
    # Cargar el archivo Excel
    df = pd.read_excel(excel_path)

    # Verificar que las columnas necesarias existan
    columnas_necesarias = ["Nombre Archivo", "Factura", "Fecha Documento", "Beneficiario", "Total"]
    if not all(col in df.columns for col in columnas_necesarias):
        print(f"El archivo Excel debe contener las columnas: {', '.join(columnas_necesarias)}")
        return

    # Recorrer cada fila del DataFrame
    for index, row in df.iterrows():
        nombre_actual = row["Nombre Archivo"]
        factura = str(row["Factura"]).strip().lower()
        fecha_doc = pd.to_datetime(row["Fecha Documento"]).strftime("%d-%m-%Y")
        beneficiario = str(row["Beneficiario"]).strip()
        total = row["Total"]

        # Crear nuevo nombre con formato: factura - fecha - beneficiario - total.pdf
        nuevo_nombre = f"{factura} - {fecha_doc} - {beneficiario} - {total}.pdf"

        # Construir rutas completas
        actual_path = os.path.join(pdf_folder, nombre_actual)
        nuevo_path = os.path.join(pdf_folder, nuevo_nombre)

        # Verificar si el archivo existe
        if os.path.exists(actual_path):
            os.rename(actual_path, nuevo_path)
            print(f"Renombrado: {nombre_actual} → {nuevo_nombre}")
        else:
            print(f"⚠️ No encontrado: {nombre_actual}")

# Ejecutar la renombración de archivos PDF
excel_path = os.path.join(output_excel, "ERP_Com_Egreso.xlsx")
renombrar_pdfs(excel_path, pdf_folder)

# Abrir la carpeta con los PDFs
os.startfile(pdf_folder)
