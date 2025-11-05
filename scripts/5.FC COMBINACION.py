import os
import fitz  # PyMuPDF
import re
import shutil
from unidecode import unidecode

# =====================================================
# 🌎 CONFIGURACIÓN UNIVERSAL DE RUTAS DINÁMICAS
# =====================================================

# Carpeta base dinámica (usa variable de entorno si existe, o /tmp por defecto)
BASE_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp")

# Crear subcarpetas para organización del procesamiento
carpeta_erp = os.path.join(BASE_FOLDER, "ERP_FACTURAS")
carpeta_documentos_soporte = os.path.join(BASE_FOLDER, "MUISKA_FACTURAS")
carpeta_combinados = os.path.join(BASE_FOLDER, "FC_EMPRESA")
carpeta_faltantes = os.path.join(BASE_FOLDER, "FALTANTES")

# Crear todas las carpetas si no existen (solo afecta localmente)
for folder in [carpeta_erp, carpeta_documentos_soporte, carpeta_combinados, carpeta_faltantes]:
    os.makedirs(folder, exist_ok=True)

# =====================================================
# 🧾 VERIFICAR LAS RUTAS CONFIGURADAS
# =====================================================
print("📁 RUTAS CONFIGURADAS:")
print(f"🧾 ERP Facturas:            {carpeta_erp}")
print(f"📄 Documentos de Soporte:   {carpeta_documentos_soporte}")
print(f"🏢 FC Empresa Combinados:   {carpeta_combinados}")
print(f"⚠️  Archivos Faltantes:     {carpeta_faltantes}")

# Crear las carpetas de salida si no existen
os.makedirs(carpeta_combinados, exist_ok=True)
os.makedirs(carpeta_faltantes, exist_ok=True)

def normalizar_fecha(fecha_raw):
    """Normaliza fecha a formato YYYY-MM-DD"""
    if not fecha_raw:
        return None
    
    partes = fecha_raw.split("-")
    if len(partes) == 3:
        d, m, a = partes
        return f"{int(a):04d}-{int(m):02d}-{int(d):02d}"  # YYYY-MM-DD
    return fecha_raw

def extraer_fecha(nombre):
    """Extrae la fecha del nombre del archivo"""
    # Buscar patrones de fecha DD-MM-YYYY
    coincidencias = re.findall(r"(\d{1,2}-\d{1,2}-\d{4})", nombre)
    if coincidencias:
        return normalizar_fecha(coincidencias[0])
    
    # Buscar patrones de fecha YYYY-MM-DD
    coincidencias = re.findall(r"(\d{4}-\d{2}-\d{2})", nombre)
    return coincidencias[0] if coincidencias else None

def extraer_valores_numericos(nombre):
    """Extrae valores numéricos del archivo, incluyendo decimales"""
    # Buscar números con decimales (comas o puntos)
    valores_decimales = re.findall(r"\d+[.,]\d+", nombre)
    valores_decimales = [float(val.replace(",", ".")) for val in valores_decimales]
    
    # Buscar números enteros
    numeros_enteros = re.findall(r"\b\d+\b", nombre)
    numeros_enteros = [int(num) for num in numeros_enteros if len(num) <= 10]  # Evitar números muy largos
    
    # Separar códigos importantes (4-6 dígitos) de otros números
    codigos_importantes = [str(num) for num in numeros_enteros if 4 <= len(str(num)) <= 6]
    otros_numeros = [str(num) for num in numeros_enteros if len(str(num)) < 4 or len(str(num)) > 6]
    
    return {
        'valores_decimales': valores_decimales,
        'codigos': codigos_importantes,
        'otros': otros_numeros,
        'todos_enteros': [str(num) for num in numeros_enteros]
    }

def extraer_nombres_persona(nombre):
    """Extrae nombres de personas del archivo - versión más flexible"""
    # Remover "FC" del inicio si existe
    nombre_limpio = re.sub(r'^FC\s*', '', nombre, flags=re.IGNORECASE)
    
    # Remover extensión
    nombre_limpio = re.sub(r'\.pdf$', '', nombre_limpio, flags=re.IGNORECASE)
    
    # Buscar patrones de nombres (2 o más palabras en mayúsculas consecutivas)
    palabras = re.sub(r'[^\w\s-]', ' ', nombre_limpio).split()
    nombres_encontrados = []
    
    i = 0
    while i < len(palabras):
        if palabras[i].isupper() and len(palabras[i]) > 2:
            nombre_completo = [palabras[i]]
            j = i + 1
            # Continuar agregando palabras en mayúsculas
            while j < len(palabras) and palabras[j].isupper() and len(palabras[j]) > 1:
                if palabras[j] not in ['DE', 'LA', 'EL', 'DEL', 'LAS', 'LOS', 'Y', 'FC']:
                    nombre_completo.append(palabras[j])
                j += 1
            
            if len(nombre_completo) >= 2:  # Al menos nombre y apellido
                nombres_encontrados.append(' '.join(nombre_completo))
            i = j
        else:
            i += 1
    
    # También intentar extraer del patrón fecha-nombre-valor
    patron = r"(\d{1,2}-\d{1,2}-\d{4})\s*-\s*(.*?)\s*-\s*(\d+[.,]?\d*)"
    coincidencia = re.search(patron, nombre_limpio)
    
    if coincidencia:
        nombre_extraido = coincidencia.group(2).strip()
        if nombre_extraido and nombre_extraido not in nombres_encontrados:
            nombres_encontrados.append(nombre_extraido.upper())
    
    return nombres_encontrados

def procesar_archivo(nombre_archivo, ruta_completa):
    """Procesa un archivo y extrae toda la información relevante"""
    valores = extraer_valores_numericos(nombre_archivo)
    nombres_personas = extraer_nombres_persona(nombre_archivo)
    fecha = extraer_fecha(nombre_archivo)
    
    return {
        'nombre_archivo': nombre_archivo,
        'ruta_completa': ruta_completa,
        'fecha': fecha,
        'valores': valores,
        'nombres_personas': nombres_personas
    }

def encontrar_coincidencias_precisas(archivos_erp, archivos_soporte):
    """Encuentra coincidencias usando criterios flexibles para facturas"""
    coincidencias = []
    indices_soporte_usados = set()
    
    for i, archivo_erp in enumerate(archivos_erp):
        mejor_coincidencia = None
        mejor_puntuacion = 0
        mejor_criterios = []
        
        for j, archivo_soporte in enumerate(archivos_soporte):
            if j in indices_soporte_usados:  # Ya fue usado
                continue
                
            puntuacion = 0
            criterios_cumplidos = []
            
            # CRITERIO 1: Fecha (flexible - no obligatorio si ambos tienen)
            fecha_coincide = True
            if archivo_erp['fecha'] and archivo_soporte['fecha']:
                if archivo_erp['fecha'] == archivo_soporte['fecha']:
                    puntuacion += 50
                    criterios_cumplidos.append(f"Fecha: {archivo_erp['fecha']}")
                else:
                    # En lugar de descartar, reducir puntuación pero permitir continuar
                    puntuacion -= 10
                    fecha_coincide = False
            elif archivo_erp['fecha'] or archivo_soporte['fecha']:
                # Solo uno tiene fecha, dar puntos menores
                fecha_disponible = archivo_erp['fecha'] or archivo_soporte['fecha']
                puntuacion += 20
                criterios_cumplidos.append(f"Fecha disponible: {fecha_disponible}")
            
            # CRITERIO 2: Valores decimales (montos) - IMPORTANTE para facturas
            valores_erp = set(archivo_erp['valores']['valores_decimales'])
            valores_soporte = set(archivo_soporte['valores']['valores_decimales'])
            valores_comunes = valores_erp & valores_soporte
            
            if valores_comunes:
                puntuacion += 40 * len(valores_comunes)
                criterios_cumplidos.append(f"Valores: {', '.join(map(str, sorted(valores_comunes)))}")
            
            # CRITERIO 3: Códigos importantes (4-6 dígitos)
            codigos_erp = set(archivo_erp['valores']['codigos'])
            codigos_soporte = set(archivo_soporte['valores']['codigos'])
            codigos_comunes = codigos_erp & codigos_soporte
            
            if codigos_comunes:
                puntuacion += 30 * len(codigos_comunes)
                criterios_cumplidos.append(f"Códigos: {', '.join(sorted(codigos_comunes))}")
            
            # CRITERIO 4: Nombres de personas (flexible - no obligatorio)
            nombres_erp = set(archivo_erp['nombres_personas'])
            nombres_soporte = set(archivo_soporte['nombres_personas'])
            nombres_comunes = nombres_erp & nombres_soporte
            
            if nombres_comunes:
                puntuacion += 35 * len(nombres_comunes)
                criterios_cumplidos.append(f"Nombres: {', '.join(nombres_comunes)}")
            
            # CRITERIO 5: Otros valores numéricos
            otros_erp = set(archivo_erp['valores']['otros'])
            otros_soporte = set(archivo_soporte['valores']['otros'])
            otros_comunes = otros_erp & otros_soporte
            
            if otros_comunes:
                puntuacion += 15 * len(otros_comunes)
                criterios_cumplidos.append(f"Otros valores: {', '.join(sorted(otros_comunes))}")
            
            # Requiere al menos 40 puntos para ser considerado válido (más flexible)
            if puntuacion >= 40 and puntuacion > mejor_puntuacion:
                mejor_puntuacion = puntuacion
                mejor_coincidencia = {
                    'archivo_soporte': archivo_soporte,
                    'puntuacion': puntuacion,
                    'criterios': criterios_cumplidos,
                    'indice_soporte': j
                }
        
        if mejor_coincidencia:
            coincidencias.append({
                'archivo_erp': archivo_erp,
                'archivo_soporte': mejor_coincidencia['archivo_soporte'],
                'puntuacion': mejor_coincidencia['puntuacion'],
                'criterios': mejor_coincidencia['criterios'],
                'indice_erp': i,
                'indice_soporte': mejor_coincidencia['indice_soporte']
            })
            indices_soporte_usados.add(mejor_coincidencia['indice_soporte'])
    
    return coincidencias

# Procesar archivos de ambas carpetas
print("🔍 PROCESANDO ARCHIVOS FACTURAS...")

archivos_erp = []
for archivo in os.listdir(carpeta_erp):
    if archivo.lower().endswith('.pdf'):
        ruta_completa = os.path.join(carpeta_erp, archivo)
        info = procesar_archivo(archivo, ruta_completa)
        archivos_erp.append(info)

archivos_soporte = []
for archivo in os.listdir(carpeta_documentos_soporte):
    if archivo.lower().endswith('.pdf'):
        ruta_completa = os.path.join(carpeta_documentos_soporte, archivo)
        info = procesar_archivo(archivo, ruta_completa)
        archivos_soporte.append(info)

print(f"📁 Archivos ERP: {len(archivos_erp)} | Archivos MUISKA: {len(archivos_soporte)}")

# Mostrar información extraída de forma organizada
print(f"\n📋 ANÁLISIS DE ARCHIVOS ERP:")
for archivo in archivos_erp:
    info_linea = []
    if archivo['fecha']:
        info_linea.append(f"📅 {archivo['fecha']}")
    if archivo['nombres_personas']:
        info_linea.append(f"👤 {', '.join(archivo['nombres_personas'])}")
    if archivo['valores']['valores_decimales']:
        info_linea.append(f"💰 {', '.join(map(str, archivo['valores']['valores_decimales']))}")
    if archivo['valores']['codigos']:
        info_linea.append(f"🔢 {', '.join(archivo['valores']['codigos'])}")
    
    print(f"   • {archivo['nombre_archivo']}")
    if info_linea:
        print(f"     └─ {' | '.join(info_linea)}")

print(f"\n📋 ANÁLISIS DE ARCHIVOS MUISKA:")
for archivo in archivos_soporte:
    info_linea = []
    if archivo['fecha']:
        info_linea.append(f"📅 {archivo['fecha']}")
    if archivo['nombres_personas']:
        info_linea.append(f"👤 {', '.join(archivo['nombres_personas'])}")
    if archivo['valores']['valores_decimales']:
        info_linea.append(f"💰 {', '.join(map(str, archivo['valores']['valores_decimales']))}")
    if archivo['valores']['codigos']:
        info_linea.append(f"🔢 {', '.join(archivo['valores']['codigos'])}")
    
    print(f"   • {archivo['nombre_archivo']}")
    if info_linea:
        print(f"     └─ {' | '.join(info_linea)}")

# Encontrar coincidencias precisas
print(f"\n🎯 BUSCANDO COINCIDENCIAS FLEXIBLES...")
coincidencias = encontrar_coincidencias_precisas(archivos_erp, archivos_soporte)

if coincidencias:
    print(f"\n✅ COINCIDENCIAS ENCONTRADAS: {len(coincidencias)}")
    for i, coincidencia in enumerate(coincidencias, 1):
        print(f"\n{i}. EMPAREJAMIENTO (Puntuación: {coincidencia['puntuacion']})")
        print(f"   📄 ERP: {coincidencia['archivo_erp']['nombre_archivo']}")
        print(f"   📄 MUISKA: {coincidencia['archivo_soporte']['nombre_archivo']}")
        print(f"   ✓ Criterios: {' | '.join(coincidencia['criterios'])}")
else:
    print(f"\n❌ NO SE ENCONTRARON COINCIDENCIAS VÁLIDAS")

# Combinar archivos usando PyMuPDF
combinados_exitosos = 0
errores = 0

if coincidencias:
    print(f"\n🔄 COMBINANDO ARCHIVOS...")
    for coincidencia in coincidencias:
        archivo_erp = coincidencia['archivo_erp']
        archivo_soporte = coincidencia['archivo_soporte']
        
        # Crear nombre de salida
        nombre_base = os.path.splitext(archivo_erp['nombre_archivo'])[0]
        nombre_salida = f"{nombre_base} - COMBINADO.pdf"
        
        ruta_salida = os.path.join(carpeta_combinados, nombre_salida)
        
        try:
            # Combinar PDFs usando PyMuPDF
            salida_pdf = fitz.open()
            salida_pdf.insert_pdf(fitz.open(archivo_erp['ruta_completa']))
            salida_pdf.insert_pdf(fitz.open(archivo_soporte['ruta_completa']))
            
            salida_pdf.save(ruta_salida)
            salida_pdf.close()
            
            print(f"✅ {nombre_salida}")
            combinados_exitosos += 1
        except Exception as e:
            print(f"❌ Error: {archivo_erp['nombre_archivo']} - {e}")
            errores += 1

# Mostrar archivos sin pareja y moverlos a carpeta FALTANTES
archivos_erp_usados = set(c['indice_erp'] for c in coincidencias)
archivos_soporte_usados = set(c['indice_soporte'] for c in coincidencias)

archivos_erp_sin_pareja = [archivos_erp[i] for i in range(len(archivos_erp)) if i not in archivos_erp_usados]
archivos_soporte_sin_pareja = [archivos_soporte[i] for i in range(len(archivos_soporte)) if i not in archivos_soporte_usados]

# Mover archivos sin pareja a carpeta FALTANTES
archivos_movidos = 0

if archivos_erp_sin_pareja:
    print(f"\n⚠️ ARCHIVOS ERP SIN PAREJA ({len(archivos_erp_sin_pareja)}):")
    for archivo in archivos_erp_sin_pareja:
        print(f"   • {archivo['nombre_archivo']}")
        try:
            destino = os.path.join(carpeta_faltantes, archivo['nombre_archivo'])
            shutil.copy2(archivo['ruta_completa'], destino)
            archivos_movidos += 1
        except Exception as e:
            print(f"     ❌ Error moviendo: {e}")

if archivos_soporte_sin_pareja:
    print(f"\n⚠️ ARCHIVOS MUISKA SIN PAREJA ({len(archivos_soporte_sin_pareja)}):")
    for archivo in archivos_soporte_sin_pareja:
        print(f"   • {archivo['nombre_archivo']}")
        try:
            destino = os.path.join(carpeta_faltantes, archivo['nombre_archivo'])
            shutil.copy2(archivo['ruta_completa'], destino)
            archivos_movidos += 1
        except Exception as e:
            print(f"     ❌ Error moviendo: {e}")

if archivos_movidos > 0:
    print(f"\n📁 Se movieron {archivos_movidos} archivos sin pareja a FALTANTES")

print(f"\n🎉 RESUMEN:")
print(f"   ✅ Combinados: {combinados_exitosos}")
print(f"   ❌ Errores: {errores}")
print(f"   📊 Tasa de éxito: {combinados_exitosos}/{len(archivos_erp)} archivos ERP")

# Abrir carpeta si se crearon archivos
if combinados_exitosos > 0:
    print(f"\n🚀 Abriendo carpeta de resultados...")
    os.startfile(carpeta_combinados)

print("\n🔍 Proceso finalizado.")