import os
import PyPDF2
import re
from app import BASE_PATHS  # si está dentro del mismo repo
import os

# Usar las rutas dinámicas centralizadas
carpeta_erp = os.path.join(BASE_PATHS["DIGITALIZACION"], "1.1 ERP COMPROBANTE DE EGRESO")
carpeta_documentos_soporte = os.path.join(BASE_PATHS["DIGITALIZACION"], "2.1 BANCO DESPRENDIBLES")
carpeta_combinados = os.path.join(BASE_PATHS["DIGITALIZACION"], "3 CE EMPRESA")

# Crear la carpeta de salida si no existe
os.makedirs(carpeta_combinados, exist_ok=True)

def extraer_fecha(nombre):
    """Extrae la fecha en formato YYYY-MM-DD del nombre del archivo"""
    coincidencias = re.findall(r"\d{4}-\d{2}-\d{2}", nombre)
    return coincidencias[0] if coincidencias else None

def extraer_valores_numericos(nombre):
    """Extrae todos los valores numéricos del archivo, priorizando códigos importantes"""
    numeros = re.findall(r"\d+", nombre)
    
    # Separar códigos importantes (4-6 dígitos) de otros números
    codigos_importantes = [num for num in numeros if 4 <= len(num) <= 6]
    otros_numeros = [num for num in numeros if len(num) < 4 or len(num) > 6]
    
    return {
        'codigos': codigos_importantes,
        'otros': otros_numeros,
        'todos': numeros
    }

def extraer_nombres_persona(nombre):
    """Extrae nombres de personas del archivo"""
    # Remover extensión y caracteres especiales
    nombre_limpio = re.sub(r'\.pdf$|\.PDF$', '', nombre)
    nombre_limpio = re.sub(r'[^\w\s-]', ' ', nombre_limpio)
    
    # Buscar patrones de nombres (2 o más palabras en mayúsculas consecutivas)
    palabras = nombre_limpio.split()
    nombres_encontrados = []
    
    i = 0
    while i < len(palabras):
        if palabras[i].isupper() and len(palabras[i]) > 2:
            nombre_completo = [palabras[i]]
            j = i + 1
            # Continuar agregando palabras en mayúsculas
            while j < len(palabras) and palabras[j].isupper() and len(palabras[j]) > 1:
                if palabras[j] not in ['DE', 'LA', 'EL', 'DEL', 'LAS', 'LOS', 'Y']:
                    nombre_completo.append(palabras[j])
                j += 1
            
            if len(nombre_completo) >= 2:  # Al menos nombre y apellido
                nombres_encontrados.append(' '.join(nombre_completo))
            i = j
        else:
            i += 1
    
    return nombres_encontrados

def procesar_archivo(nombre_archivo, ruta_completa):
    """Procesa un archivo y extrae toda la información relevante"""
    valores = extraer_valores_numericos(nombre_archivo)
    return {
        'nombre_archivo': nombre_archivo,
        'ruta_completa': ruta_completa,
        'fecha': extraer_fecha(nombre_archivo),
        'valores': valores,
        'nombres_personas': extraer_nombres_persona(nombre_archivo)
    }

def encontrar_coincidencias_precisas(archivos_erp, archivos_soporte):
    """Encuentra coincidencias usando criterios precisos"""
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
            
            # CRITERIO 1: Fecha exacta (obligatorio si ambos tienen fecha)
            fecha_coincide = True
            if archivo_erp['fecha'] and archivo_soporte['fecha']:
                if archivo_erp['fecha'] == archivo_soporte['fecha']:
                    puntuacion += 50
                    criterios_cumplidos.append(f"Fecha: {archivo_erp['fecha']}")
                else:
                    fecha_coincide = False  # Si ambos tienen fecha y no coinciden, descartar
            elif archivo_erp['fecha'] or archivo_soporte['fecha']:
                # Solo uno tiene fecha, dar puntos menores
                fecha_disponible = archivo_erp['fecha'] or archivo_soporte['fecha']
                puntuacion += 20
                criterios_cumplidos.append(f"Fecha disponible: {fecha_disponible}")
            
            if not fecha_coincide:
                continue  # Descartar si las fechas no coinciden
            
            # CRITERIO 2: Códigos importantes (4-6 dígitos)
            codigos_erp = set(archivo_erp['valores']['codigos'])
            codigos_soporte = set(archivo_soporte['valores']['codigos'])
            codigos_comunes = codigos_erp & codigos_soporte
            
            if codigos_comunes:
                puntuacion += 40 * len(codigos_comunes)
                criterios_cumplidos.append(f"Códigos: {', '.join(sorted(codigos_comunes))}")
            
            # CRITERIO 3: Otros valores numéricos
            otros_erp = set(archivo_erp['valores']['otros'])
            otros_soporte = set(archivo_soporte['valores']['otros'])
            otros_comunes = otros_erp & otros_soporte
            
            if otros_comunes:
                puntuacion += 10 * len(otros_comunes)
                criterios_cumplidos.append(f"Otros valores: {', '.join(sorted(otros_comunes))}")
            
            # CRITERIO 4: Nombres de personas (coincidencia exacta)
            nombres_erp = set(archivo_erp['nombres_personas'])
            nombres_soporte = set(archivo_soporte['nombres_personas'])
            nombres_comunes = nombres_erp & nombres_soporte
            
            if nombres_comunes:
                puntuacion += 30 * len(nombres_comunes)
                criterios_cumplidos.append(f"Nombres: {', '.join(nombres_comunes)}")
            
            # Requiere al menos 60 puntos para ser considerado válido
            if puntuacion >= 60 and puntuacion > mejor_puntuacion:
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
print("🔍 PROCESANDO ARCHIVOS...")

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

print(f"📁 Archivos ERP: {len(archivos_erp)} | Archivos Soporte: {len(archivos_soporte)}")

# Mostrar información extraída de forma organizada
print(f"\n📋 ANÁLISIS DE ARCHIVOS ERP:")
for archivo in archivos_erp:
    info_linea = []
    if archivo['fecha']:
        info_linea.append(f"📅 {archivo['fecha']}")
    if archivo['valores']['codigos']:
        info_linea.append(f"🔢 {', '.join(archivo['valores']['codigos'])}")
    if archivo['nombres_personas']:
        info_linea.append(f"👤 {', '.join(archivo['nombres_personas'])}")
    
    print(f"   • {archivo['nombre_archivo']}")
    if info_linea:
        print(f"     └─ {' | '.join(info_linea)}")

print(f"\n📋 ANÁLISIS DE ARCHIVOS SOPORTE:")
for archivo in archivos_soporte:
    info_linea = []
    if archivo['fecha']:
        info_linea.append(f"📅 {archivo['fecha']}")
    if archivo['valores']['codigos']:
        info_linea.append(f"🔢 {', '.join(archivo['valores']['codigos'])}")
    if archivo['nombres_personas']:
        info_linea.append(f"👤 {', '.join(archivo['nombres_personas'])}")
    
    print(f"   • {archivo['nombre_archivo']}")
    if info_linea:
        print(f"     └─ {' | '.join(info_linea)}")

# Encontrar coincidencias precisas
print(f"\n🎯 BUSCANDO COINCIDENCIAS PRECISAS...")
coincidencias = encontrar_coincidencias_precisas(archivos_erp, archivos_soporte)

if coincidencias:
    print(f"\n✅ COINCIDENCIAS ENCONTRADAS: {len(coincidencias)}")
    for i, coincidencia in enumerate(coincidencias, 1):
        print(f"\n{i}. EMPAREJAMIENTO (Puntuación: {coincidencia['puntuacion']})")
        print(f"   📄 ERP: {coincidencia['archivo_erp']['nombre_archivo']}")
        print(f"   📄 Soporte: {coincidencia['archivo_soporte']['nombre_archivo']}")
        print(f"   ✓ Criterios: {' | '.join(coincidencia['criterios'])}")
else:
    print(f"\n❌ NO SE ENCONTRARON COINCIDENCIAS VÁLIDAS")

# Combinar archivos
combinados_exitosos = 0
errores = 0

if coincidencias:
    print(f"\n🔄 COMBINANDO ARCHIVOS...")
    for coincidencia in coincidencias:
        archivo_erp = coincidencia['archivo_erp']
        archivo_soporte = coincidencia['archivo_soporte']
        
        # Crear nombre de salida usando la fecha del soporte (prioritaria) o del ERP
        fecha_para_nombre = archivo_soporte['fecha'] or archivo_erp['fecha']
        nombre_base = archivo_erp['nombre_archivo'][:-4]  # Quitar .pdf
        
        if fecha_para_nombre:
            nombre_salida = f"{nombre_base}-{fecha_para_nombre}.pdf"
        else:
            nombre_salida = f"{nombre_base}-COMBINADO.pdf"
        
        ruta_salida = os.path.join(carpeta_combinados, nombre_salida)
        
        try:
            # Crear el PDF combinado
            pdf_merger = PyPDF2.PdfMerger()
            pdf_merger.append(archivo_erp['ruta_completa'])
            pdf_merger.append(archivo_soporte['ruta_completa'])
            pdf_merger.write(ruta_salida)
            pdf_merger.close()
            
            print(f"✅ {nombre_salida}")
            combinados_exitosos += 1
        except Exception as e:
            print(f"❌ Error: {archivo_erp['nombre_archivo']} - {e}")
            errores += 1

# Mostrar archivos sin pareja
archivos_erp_usados = set(c['indice_erp'] for c in coincidencias)
archivos_soporte_usados = set(c['indice_soporte'] for c in coincidencias)

archivos_erp_sin_pareja = [archivos_erp[i] for i in range(len(archivos_erp)) if i not in archivos_erp_usados]
archivos_soporte_sin_pareja = [archivos_soporte[i] for i in range(len(archivos_soporte)) if i not in archivos_soporte_usados]

if archivos_erp_sin_pareja:
    print(f"\n⚠️ ARCHIVOS ERP SIN PAREJA ({len(archivos_erp_sin_pareja)}):")
    for archivo in archivos_erp_sin_pareja:
        print(f"   • {archivo['nombre_archivo']}")

if archivos_soporte_sin_pareja:
    print(f"\n⚠️ ARCHIVOS SOPORTE SIN PAREJA ({len(archivos_soporte_sin_pareja)}):")
    for archivo in archivos_soporte_sin_pareja:
        print(f"   • {archivo['nombre_archivo']}")

print(f"\n🎉 RESUMEN:")
print(f"   ✅ Combinados: {combinados_exitosos}")
print(f"   ❌ Errores: {errores}")
print(f"   📊 Tasa de éxito: {combinados_exitosos}/{len(archivos_erp)} archivos ERP")

# Ruta de la carpeta con los archivos combinados
carpeta_combinados = os.path.join(os.getenv('USERPROFILE'), r"OneDrive\2 PROYECTOS TECNOLOGIA\2 AUTOMAIZACION TECNOLOGIA\2.RESULTADOS\1.DIGITALIZACION\3 CE EMPRESA")

# Crear la carpeta si no existe
if not os.path.exists(carpeta_combinados):
    os.makedirs(carpeta_combinados)


