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
# ⚙️ EJECUTAR SCRIPT SELECCIONADO
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

        if result.returncode == 0:
            return jsonify({
                "message": f"✅ {filename} ejecutado correctamente",
                "output": result.stdout
            })
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
