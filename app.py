from flask import Flask, jsonify, render_template, request
import os
import subprocess

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
    """Carga la interfaz principal"""
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
# 📤 SUBIR PDFs (campo HTML: name="pdfFiles")
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
# ⚙️ EJECUTAR SCRIPT SELECCIONADO Y ENVIAR RESULTADO A DESCARGAS
# ==============================================
@app.route("/run-process1/<filename>", methods=["POST"])
def run_process(filename):
    script_path = os.path.join(SCRIPTS_PATH, filename)
    if not os.path.exists(script_path):
        return jsonify({"error": f"❌ Archivo {filename} no encontrado"}), 404

    try:
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            cwd=SCRIPTS_PATH
        )

        # 📁 Crear carpeta de resultados según entorno
        if os.name == "nt":  # Windows local
            resultado_path = os.path.join(os.path.expanduser("~"), "Downloads", "resultado")
        else:  # Render o Linux
            resultado_path = "/tmp/resultado"

        os.makedirs(resultado_path, exist_ok=True)

        # 📦 Mover archivos generados (PDF, XLSX, CSV)
        moved_files = []
        for file in os.listdir(SCRIPTS_PATH):
            if file.lower().endswith((".pdf", ".xlsx", ".csv")):
                src = os.path.join(SCRIPTS_PATH, file)
                dst = os.path.join(resultado_path, file)
                os.replace(src, dst)
                moved_files.append(file)

        # 🔗 Construir mensaje de salida
        if result.returncode == 0:
            msg = {
                "message": f"✅ {filename} ejecutado correctamente",
                "output": result.stdout,
                "archivos_movidos": moved_files,
                "carpeta_resultado": resultado_path
            }

            # Si estás en Render, agrega URL pública (opcional)
            render_url = os.environ.get("RENDER_EXTERNAL_URL")
            if render_url:
                msg["download_url"] = f"{render_url}/download/resultado"

            return jsonify(msg)
        else:
            return jsonify({
                "error": f"❌ Error ejecutando {filename}",
                "details": result.stderr
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================
# 🚀 INICIAR SERVIDOR
# ==============================================
if __name__ == "__main__":
    print("🚀 Servidor Flask corriendo...")
    print("📂 Scripts:", SCRIPTS_PATH)
    print("📁 Uploads:", UPLOADS_PATH)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
