from flask import Flask, jsonify, render_template, request, send_from_directory
import os
import subprocess
import shutil

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

    # 🔥 AQUÍ ESTÁ EL FIX: Calcular la carpeta de uploads para este script
    folder_name = filename.split(".py")[0].replace(" ", "_").replace(".", "_")
    upload_folder = os.path.join(UPLOADS_PATH, folder_name)

    try:
        # 🔥 PASAR LA CARPETA COMO ARGUMENTO AL SCRIPT
        result = subprocess.run(
            ["python", script_path, upload_folder],  # ✅ Argumento añadido
            capture_output=True,
            text=True,
            cwd=SCRIPTS_PATH,
            timeout=300  # 5 minutos máximo
        )

        print(f"📋 STDOUT del script:\n{result.stdout}")
        print(f"📋 STDERR del script:\n{result.stderr}")

        # 📂 Carpeta destino según entorno
        if os.name == "nt":  # Windows local
            resultado_path = os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
        else:  # Render o Linux
            resultado_path = "/tmp/resultado"
        os.makedirs(resultado_path, exist_ok=True)

        # 🔥 BUSCAR ARCHIVOS EN DOS LUGARES:
        # 1. En la carpeta de uploads (donde el script los genera)
        # 2. En la carpeta de scripts (por si acaso)
        moved_files = []
        
        # Buscar en carpeta de uploads
        for file in os.listdir(upload_folder):
            if file.lower().endswith((".pdf", ".xlsx", ".csv")):
                src = os.path.join(upload_folder, file)
                dst = os.path.join(resultado_path, file)
                shutil.copy2(src, dst)
                moved_files.append(file)
                print(f"✅ Copiado desde uploads: {file}")

        # Buscar en carpeta de scripts (backup)
        for file in os.listdir(SCRIPTS_PATH):
            if file.lower().endswith((".pdf", ".xlsx", ".csv")) and file not in moved_files:
                src = os.path.join(SCRIPTS_PATH, file)
                dst = os.path.join(resultado_path, file)
                shutil.copy2(src, dst)
                moved_files.append(file)
                print(f"✅ Copiado desde scripts: {file}")

        # 🔎 URL de descarga (solo si Render)
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        download_url = f"{render_url}/download/resultado" if render_url else None

        # 🧾 Respuesta
        return jsonify({
            "message": f"✅ {filename} ejecutado correctamente",
            "output": result.stdout,
            "error_output": result.stderr if result.stderr else None,
            "archivos_guardados": moved_files,
            "carpeta_resultado": resultado_path,
            "download_url": download_url,
            "total_archivos": len(moved_files)
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "⏱️ El proceso excedió el tiempo máximo de 5 minutos"}), 500
    except Exception as e:
        print(f"❌ Error completo: {str(e)}")
        return jsonify({"error": f"Error: {str(e)}"}), 500

# ==============================================
# 📥 DESCARGAR RESULTADOS DESDE RENDER
# ==============================================
@app.route("/download/resultado/<path:filename>", methods=["GET"])
def download_file(filename):
    resultado_path = "/tmp/resultado" if not os.name == "nt" else os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
    return send_from_directory(resultado_path, filename, as_attachment=True)

@app.route("/ver-resultados", methods=["GET"])
def ver_resultados():
    resultado_path = "/tmp/resultado" if not os.name == "nt" else os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
    
    if not os.path.exists(resultado_path):
        return jsonify({"archivos_encontrados": []})
    
    archivos = [f for f in os.listdir(resultado_path) if os.path.isfile(os.path.join(resultado_path, f))]
    return jsonify({"archivos_encontrados": archivos})

# ==============================================
# 🚀 INICIAR SERVIDOR
# ==============================================
if __name__ == "__main__":
    print("🚀 Servidor Flask corriendo...")
    print("📂 Scripts:", SCRIPTS_PATH)
    print("📁 Uploads:", UPLOADS_PATH)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))