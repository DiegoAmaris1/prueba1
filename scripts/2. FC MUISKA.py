import os
import csv
import re
import pdfplumber
from datetime import datetime

# ==============================================================
# 📂 CONFIGURACIÓN AUTOMÁTICA DE RUTAS (compatible con Flask)
# ==============================================================

# Detectar carpeta del proyecto
base_path = os.getcwd()

# Si Flask envía la ruta por argumento (al ejecutar el script)
if len(sys.argv) > 1:
    carpeta_documentos = sys.argv[1]
else:
    # Detectar automáticamente según el nombre del script
    script_name = os.path.basename(__file__)
    carpeta_nombre = "_" + script_name.replace(".py", "").replace(" ", "_").replace(".", "_")

    carpeta_documentos = os.path.join(base_path, "uploads", carpeta_nombre)

# Crear la carpeta si no existe
os.makedirs(carpeta_documentos, exist_ok=True)

# Ruta de salida (por ejemplo CSV o Excel)
archivo_salida = os.path.join(carpeta_documentos, f"resultado_{os.path.basename(__file__).replace('.py', '')}.xlsx")

print(f"📁 Carpeta de trabajo: {carpeta_documentos}")
print(f"💾 Archivo de salida: {archivo_salida}")

# Expresiones regulares mejoradas para fechas
patrones_fecha = [
    re.compile(r"Fecha de Emisión:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE),
    re.compile(r"Fecha de generación:\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    re.compile(r"Fecha y hora de expedición:\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    re.compile(r"Fecha de hora de expedición:\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE),
]

# Expresiones regulares mejoradas para razón social
patrones_razon_social = [
    re.compile(r"Datos del Emisor / Vendedor[\s\S]*?Razón Social:\s*([^:\n]+?)(?:\s*\n|Nombre Comercial:)", re.IGNORECASE),
    re.compile(r"Razón Social:\s*([^:\n]+?)(?:\s*\n|Nombre Comercial:)", re.IGNORECASE),
    re.compile(r"Razón social:\s*([^:\n]+?)(?:\s*\n|Tipo de documento:)", re.IGNORECASE),
    re.compile(r"Datos del vendedor\s*\nRazón social:\s*([^:\n]+?)\s*\n", re.IGNORECASE),
    re.compile(r"Proveedo:\s*([^:\n]+?)(?:\s*\n|NIT:)", re.IGNORECASE),
]

# Expresiones regulares mejoradas para valores monetarios
patrones_valor = [
    (re.compile(r"MONEDA\s+COP\s+TASA DE CAMBIO\s+Subtotal\s+([\d\.\,]+)", re.IGNORECASE | re.DOTALL), "Subtotal COP"),
    (re.compile(r"Subtotal\s+([\d\.\,]+)", re.IGNORECASE), "Subtotal"),
    (re.compile(r"Total neto factura \(=\)\s+([\d\.\,]+)", re.IGNORECASE), "Total Neto Factura"),
    (re.compile(r"Total neto documento \(=\)\s*[:$]?\s*([\d\.\,]+)", re.IGNORECASE), "Total Neto Documento"),
    (re.compile(r"Total factura \(=\)[\s\$]*COP\s*\$\s*([\d\.\,]+)", re.IGNORECASE), "Total Factura"),
    (re.compile(r"COP\s*\$\s*([\d\.\,]+)(?:\s|$)", re.IGNORECASE), "Valor COP"),
]

datos_extraidos = []

# Función para limpiar valores numéricos
def limpiar_valor(valor):
    if not valor:
        return None
    try:
        # Remover puntos como separadores de miles y convertir comas a puntos decimales
        valor_str = str(valor).replace(".", "").replace(",", ".")
        valor_float = float(valor_str)
        return int(valor_float) if valor_float.is_integer() else valor_float
    except (ValueError, TypeError):
        return None

# Función para extraer fecha
def extraer_fecha(texto):
    for patron in patrones_fecha:
        try:
            match = patron.search(texto)
            if match:
                return match.group(1)
        except (AttributeError, IndexError):
            continue
    return None

# Función para extraer razón social
def extraer_razon_social(texto):
    for patron in patrones_razon_social:
        try:
            match = patron.search(texto)
            if match:
                razon_social = match.group(1).strip()
                # Limpiar caracteres no deseados
                razon_social = re.sub(r'[\n\r\t]+', ' ', razon_social)
                razon_social = re.sub(r'\s+', ' ', razon_social)
                return razon_social.strip()
        except (AttributeError, IndexError):
            continue
    return None

# Función para extraer valor monetario
def extraer_valor(texto):
    for patron, fuente in patrones_valor:
        try:
            match = patron.search(texto)
            if match:
                valor_texto = match.group(1)
                valor_limpio = limpiar_valor(valor_texto)
                if valor_limpio and valor_limpio > 1000:  # Filtrar valores muy pequeños
                    return valor_limpio, fuente
        except (AttributeError, IndexError):
            continue
    
    # Modo forzado: buscar números grandes después de "subtotal"
    try:
        idx = texto.lower().find("subtotal")
        if idx != -1:
            posterior = texto[idx: idx + 500]
            # Buscar números con formato de moneda colombiana
            num_matches = re.findall(r"([\d\.\,]+)", posterior)
            for num in num_matches:
                valor_limpio = limpiar_valor(num)
                if valor_limpio and valor_limpio > 50000:  # Valores significativos
                    return valor_limpio, "Modo Forzado (Subtotal)"
        
        # Buscar directamente valores COP con $
        cop_matches = re.findall(r"COP\s*\$\s*([\d\.\,]+)", texto, re.IGNORECASE)
        for num in cop_matches:
            valor_limpio = limpiar_valor(num)
            if valor_limpio and valor_limpio > 50000:
                return valor_limpio, "Modo Forzado (COP)"
                
    except Exception:
        pass
    
    return None, None

# Función para extraer texto de manera más robusta
def extraer_texto_pdf(ruta_pdf):
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto_completo = ""
            for i, page in enumerate(pdf.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        texto_completo += page_text + "\n"
                except Exception as e:
                    print(f"    ⚠ Error en página {i+1}: {str(e)}")
                    continue
            return texto_completo
    except Exception as e:
        print(f"    ❌ Error abriendo PDF: {str(e)}")
        return None

# Procesar PDFs
print("🔄 Iniciando procesamiento de PDFs...")
archivos_procesados = 0
archivos_exitosos = 0

for archivo in os.listdir(carpeta_documentos):
    if archivo.lower().endswith(".pdf"):
        archivos_procesados += 1
        ruta_pdf = os.path.join(carpeta_documentos, archivo)
        print(f"\n📄 Procesando [{archivos_procesados}]: {archivo}")
        
        # Extraer texto del PDF
        texto_completo = extraer_texto_pdf(ruta_pdf)
        
        if not texto_completo or not texto_completo.strip():
            print(f"  ⚠ Archivo sin texto extraíble")
            continue
        
        # Limpiar y normalizar texto
        texto_limpio = re.sub(r'\s+', ' ', texto_completo)
        texto_limpio = re.sub(r'(\w)(Subtotal)', r'\1 \2', texto_limpio)
        
        # Debug: mostrar una muestra del texto extraído
        print(f"  📝 Muestra del texto: {texto_limpio[:200]}...")
        
        # Extraer información
        fecha_expedicion = extraer_fecha(texto_limpio)
        razon_social = extraer_razon_social(texto_limpio)
        valor_extraido, fuente_valor = extraer_valor(texto_limpio)
        
        # Mostrar resultados de extracción
        print(f"  📅 Fecha extraída: {fecha_expedicion}")
        print(f"  🏢 Razón Social extraída: {razon_social}")
        print(f"  💰 Valor extraído: {valor_extraido} (Fuente: {fuente_valor})")
        
        # Validar información extraída
        if fecha_expedicion and razon_social and valor_extraido:
            # Convertir formato de fecha si es necesario
            fecha_final = fecha_expedicion
            if "-" in fecha_expedicion:
                try:
                    anio, mes, dia = fecha_expedicion.split("-")
                    fecha_final = f"{dia}/{mes}/{anio}"
                except ValueError:
                    print(f"  ⚠ Error al convertir fecha: {fecha_expedicion}")
                    continue
            
            datos_extraidos.append([
                fecha_final, 
                razon_social, 
                valor_extraido, 
                fuente_valor, 
                archivo
            ])
            archivos_exitosos += 1
            print(f"  ✅ Procesado exitosamente")
        else:
            print(f"  ❌ Información incompleta:")
            print(f"    - Fecha: {'✓' if fecha_expedicion else '✗'}")
            print(f"    - Razón Social: {'✓' if razon_social else '✗'}")
            print(f"    - Valor: {'✓' if valor_extraido else '✗'}")
            
            # Si no encuentra nada, mostrar más texto para debug
            if not fecha_expedicion and not razon_social and not valor_extraido:
                print(f"  🔍 Texto completo para debug:")
                print(f"      {texto_limpio[:500]}...")

print(f"\n📊 Resumen del procesamiento:")
print(f"   - Archivos totales: {archivos_procesados}")
print(f"   - Procesados exitosamente: {archivos_exitosos}")
print(f"   - Fallidos: {archivos_procesados - archivos_exitosos}")

# Ordenar por fecha
def convertir_fecha(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y")
    except ValueError:
        try:
            return datetime.strptime(fecha_str, "%Y-%m-%d")
        except ValueError:
            return datetime.min

if datos_extraidos:
    datos_extraidos.sort(key=lambda x: convertir_fecha(x[0]))

# Guardar CSV
if datos_extraidos:
    try:
        with open(archivo_salida, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["Fecha", "Razón Social Proveedores", "Subtotal/Total", "Fuente del Valor", "Nombre del Archivo"])
            writer.writerows(datos_extraidos)
        print(f"\n✅ Archivo CSV generado exitosamente en: {archivo_salida}")
    except PermissionError:
        print("\n⚠ ERROR: El archivo CSV está abierto en otro programa.")
        input("Cierra el archivo CSV y presiona Enter para continuar...")
        try:
            with open(archivo_salida, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(["Fecha", "Razón Social Proveedores", "Subtotal/Total", "Fuente del Valor", "Nombre del Archivo"])
                writer.writerows(datos_extraidos)
            print(f"✅ Archivo CSV generado exitosamente en: {archivo_salida}")
        except Exception as e:
            print(f"❌ Error final al guardar CSV: {str(e)}")
            exit()
    except Exception as e:
        print(f"❌ Error al guardar CSV: {str(e)}")
        exit()
else:
    print("\n⚠ No se encontraron documentos válidos para procesar.")
    print("💡 Revisa que los PDFs contengan facturas electrónicas válidas.")
    exit()

# Renombrar PDFs
print("\n🔄 Iniciando renombrado de archivos...")

nombres_archivos = {}
try:
    with open(archivo_salida, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)  # Saltar encabezado
        
        for fila in reader:
            if len(fila) >= 5:
                fecha = fila[0].strip().replace("/", "-")
                razon_social = fila[1].strip()
                subtotal = str(int(float(fila[2]))).strip()  # Convertir a entero para nombres más limpios
                nombre_archivo = fila[4].strip()
                
                # Limpiar razón social para nombre de archivo
                razon_social_limpia = re.sub(r'[<>:"/\\|?*]', '', razon_social)
                razon_social_limpia = re.sub(r'\s+', ' ', razon_social_limpia)
                razon_social_limpia = razon_social_limpia[:60]  # Limitar longitud
                
                if nombre_archivo:
                    nuevo_nombre = f"{fecha} - {razon_social_limpia} - ${subtotal}.pdf"
                    nombres_archivos[nombre_archivo] = nuevo_nombre

    # Renombrar archivos
    archivos_renombrados = 0
    for archivo in os.listdir(carpeta_documentos):
        if archivo.lower().endswith(".pdf"):
            if archivo in nombres_archivos:
                ruta_original = os.path.join(carpeta_documentos, archivo)
                nuevo_nombre = nombres_archivos[archivo]
                ruta_nueva = os.path.join(carpeta_documentos, nuevo_nombre)
                
                if os.path.exists(ruta_nueva):
                    print(f"✅ Ya tiene nombre correcto: {nuevo_nombre}")
                    continue
                
                try:
                    os.rename(ruta_original, ruta_nueva)
                    print(f"✅ Renombrado: {archivo} → {nuevo_nombre}")
                    archivos_renombrados += 1
                except Exception as e:
                    print(f"❌ Error renombrando {archivo}: {str(e)}")

    print(f"\n📁 Archivos renombrados: {archivos_renombrados}")

except Exception as e:
    print(f"❌ Error durante el renombrado: {str(e)}")

print(f"\n🎉 Proceso completado.")
print(f"📊 Resumen final:")
print(f"   - Archivos procesados: {archivos_procesados}")
print(f"   - Extracciones exitosas: {archivos_exitosos}")
print(f"   - Archivos renombrados: {archivos_renombrados if 'archivos_renombrados' in locals() else 0}")
print(f"   - Archivo CSV: {archivo_salida}")

# Intentar abrir la carpeta
try:
    os.startfile(carpeta_documentos)
    print(f"📂 Carpeta abierta: {carpeta_documentos}")
except Exception as e:
    print(f"⚠ Abre manualmente: {carpeta_documentos}")
