from flask import Flask, jsonify, render_template, request, send_from_directory
import os
import subprocess
import shutil
import time

# ==============================================
# 🔧 CONFIGURACIÓN PRINCIPAL
# ==============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# 📁 Carpetas de trabajo
SCRIPTS_PATH = os.path.join(BASE_DIR, "scripts")
UPLOADS_PATH = os.path.join(BASE_DIR, "uploads")
os.makedirs(SCRIPTS_PATH, exist_ok=True)
os.makedirs(UPLOADS_PATH, exist_ok=True)

# 📜 Lista de scripts esperados
EXPECTED_SCRIPTS = [
    "1.ERP FC.py",
    "2. FC MUISKA.py",
    "3.CE DESPRENDIBLES.py",
    "4.CE ERP CONTABLE.py",
    "5.FC COMBINACION.py",
    "6 CE COMBINADO.py"
]

# Crear subcarpetas dentro de uploads (una por script)
for script in EXPECTED_SCRIPTS:
    folder_name = script.split(".py")[0].replace(" ", "_").replace(".", "_")
    os.makedirs(os.path.join(UPLOADS_PATH, folder_name), exist_ok=True)

# ==============================================
# 🌐 RUTA PRINCIPAL
# ==============================================
@app.route("/")
def index():
    return render_template("procesador-documentos-pdf.html")

# ==============================================
# 📂 VERIFICAR SCRIPTS DISPONIBLES
# ==============================================
@app.route("/check-files", methods=["GET"])
def check_files():
    files_status = []
    for filename in EXPECTED_SCRIPTS:
        path = os.path.join(SCRIPTS_PATH, filename)
        files_status.append({"name": filename, "exists": os.path.exists(path)})
    return jsonify(files_status)

# ==============================================
# 📤 SUBIR PDFs
# ==============================================
@app.route("/upload-pdfs1/<filename>", methods=["POST"])
def upload_pdfs(filename):
    if filename not in EXPECTED_SCRIPTS:
        return jsonify({"error": f"❌ Proceso '{filename}' no reconocido"}), 404

    folder_name = filename.split(".py")[0].replace(" ", "_").replace(".", "_")
    target_folder = os.path.join(UPLOADS_PATH, folder_name)
    os.makedirs(target_folder, exist_ok=True)

    if "pdfFiles" not in request.files:
        return jsonify({"error": "⚠ No se enviaron archivos (campo 'pdfFiles' vacío)"}), 400

    files = request.files.getlist("pdfFiles")
    saved = []

    for file in files:
        if file.filename.lower().endswith(".pdf"):
            save_path = os.path.join(target_folder, file.filename)
            file.save(save_path)
            saved.append(file.filename)

    if not saved:
        return jsonify({"error": "⚠ No se encontraron archivos PDF válidos"}), 400

    return jsonify({
        "message": f"✅ {len(saved)} archivo(s) subido(s) correctamente para {filename}",
        "saved_files": saved
    })

# ==============================================
# ⚙️ EJECUTAR SCRIPT Y GUARDAR RESULTADO EN DESCARGAS
# ==============================================
@app.route("/run-process1/<filename>", methods=["POST"])
def run_process(filename):
    script_path = os.path.join(SCRIPTS_PATH, filename)
    if not os.path.exists(script_path):
        return jsonify({"error": f"❌ Archivo {filename} no encontrado"}), 404

    # 🔥 Calcular la carpeta de uploads para este script
    folder_name = filename.split(".py")[0].replace(" ", "_").replace(".", "_")
    upload_folder = os.path.join(UPLOADS_PATH, folder_name)

    # 📂 Carpeta destino según entorno
    if os.name == "nt":  # Windows local
        resultado_path = os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
    else:  # Render o Linux
        resultado_path = "/tmp/resultado"
    os.makedirs(resultado_path, exist_ok=True)

    # 🗑️ Limpiar carpeta de resultados antes de ejecutar
    for file in os.listdir(resultado_path):
        file_path = os.path.join(resultado_path, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"⚠️ No se pudo eliminar {file}: {e}")

    try:
        # 🔥 PASAR LA CARPETA COMO ARGUMENTO AL SCRIPT
        print(f"🚀 Ejecutando script: {script_path}")
        print(f"📁 Carpeta de trabajo: {upload_folder}")
        
        result = subprocess.run(
            ["python", script_path, upload_folder],
            capture_output=True,
            text=True,
            cwd=SCRIPTS_PATH,
            timeout=300  # 5 minutos máximo
        )

        print(f"📋 STDOUT del script:\n{result.stdout}")
        if result.stderr:
            print(f"📋 STDERR del script:\n{result.stderr}")

        # ⏳ Esperar un momento para que el script termine de escribir archivos
        time.sleep(2)

        # 🔥 BUSCAR ARCHIVOS GENERADOS
        moved_files = []
        
        print(f"🔍 Buscando archivos en: {upload_folder}")
        if os.path.exists(upload_folder):
            archivos_en_upload = os.listdir(upload_folder)
            print(f"📄 Archivos encontrados: {len(archivos_en_upload)}")
            
            for file in archivos_en_upload:
                # Copiar archivos de resultado (Excel, CSV) y PDFs procesados
                if file.lower().endswith((".pdf", ".xlsx", ".csv", ".xls")):
                    src = os.path.join(upload_folder, file)
                    dst = os.path.join(resultado_path, file)
                    
                    try:
                        shutil.copy2(src, dst)
                        moved_files.append(file)
                        print(f"✅ Copiado: {file} ({os.path.getsize(src)} bytes)")
                    except Exception as e:
                        print(f"❌ Error copiando {file}: {e}")

        # También buscar en carpeta de scripts (backup)
        print(f"🔍 Buscando archivos en: {SCRIPTS_PATH}")
        if os.path.exists(SCRIPTS_PATH):
            for file in os.listdir(SCRIPTS_PATH):
                if file.lower().endswith((".xlsx", ".csv", ".xls")) and file not in moved_files:
                    src = os.path.join(SCRIPTS_PATH, file)
                    dst = os.path.join(resultado_path, file)
                    
                    try:
                        shutil.copy2(src, dst)
                        moved_files.append(file)
                        print(f"✅ Copiado desde scripts: {file}")
                    except Exception as e:
                        print(f"❌ Error copiando {file}: {e}")

        # 🔎 Verificar qué quedó en la carpeta de resultados
        archivos_finales = os.listdir(resultado_path)
        print(f"📊 Archivos en carpeta resultado: {archivos_finales}")

        # 🔗 URL de descarga (solo si Render)
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        download_urls = []
        if render_url:
            for file in moved_files:
                download_urls.append({
                    "filename": file,
                    "url": f"{render_url}/download/resultado/{file}"
                })

        # 🧾 Respuesta
        return jsonify({
            "message": f"✅ {filename} ejecutado correctamente",
            "output": result.stdout,
            "error_output": result.stderr if result.stderr else None,
            "archivos_guardados": moved_files,
            "carpeta_resultado": resultado_path,
            "download_urls": download_urls if render_url else None,
            "total_archivos": len(moved_files),
            "success": len(moved_files) > 0
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "⏱️ El proceso excedió el tiempo máximo de 5 minutos"}), 500
    except Exception as e:
        print(f"❌ Error completo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500

# ==============================================
# 📥 DESCARGAR RESULTADOS DESDE RENDER
# ==============================================
@app.route("/download/resultado/<path:filename>", methods=["GET"])
def download_file(filename):
    resultado_path = "/tmp/resultado" if not os.name == "nt" else os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
    
    file_path = os.path.join(resultado_path, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": f"Archivo {filename} no encontrado"}), 404
    
    return send_from_directory(resultado_path, filename, as_attachment=True)

@app.route("/ver-resultados", methods=["GET"])
def ver_resultados():
    resultado_path = "/tmp/resultado" if not os.name == "nt" else os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
    
    if not os.path.exists(resultado_path):
        return jsonify({"archivos_encontrados": []})
    
    archivos = []
    for f in os.listdir(resultado_path):
        file_path = os.path.join(resultado_path, f)
        if os.path.isfile(file_path):
            archivos.append({
                "nombre": f,
                "tamaño": os.path.getsize(file_path),
                "url": f"/download/resultado/{f}"
            })
    
    return jsonify({"archivos_encontrados": archivos})

# ==============================================
# 🚀 INICIAR SERVIDOR
# ==============================================
if __name__ == "__main__":
    print("🚀 Servidor Flask corriendo...")
    print("📂 Scripts:", SCRIPTS_PATH)
    print("📁 Uploads:", UPLOADS_PATH)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))