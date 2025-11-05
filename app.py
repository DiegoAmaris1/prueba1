from flask import Flask, jsonify, render_template, request, send_from_directory
import os
import subprocess
import shutil

app = Flask(__name__, template_folder="templates")

# ==============================================
# 🔧 CONFIGURACIÓN DE RUTAS
# ==============================================
SCRIPTS_PATH = r"C:\Users\Usuario\Downloads\scripts"
UPLOADS_PATH = os.path.join(SCRIPTS_PATH, "uploads")
OUTPUT_PATH = os.path.join(os.path.expanduser("~"), "Downloads")  # carpeta Descargas local

os.makedirs(UPLOADS_PATH, exist_ok=True)
os.makedirs(OUTPUT_PATH, exist_ok=True)

EXPECTED_SCRIPTS = [
    "1.ERP FC.py",
    "2. FC MUISKA.py",
    "3.CE DESPRENDIBLES.py",
    "4.CE ERP CONTABLE.py",
    "5.FC COMBINACION.py",
    "6 CE COMBINADO.py"
]

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
# ⚙️ EJECUTAR SCRIPT Y ENVIAR A DESCARGAS
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

        # Si el script generó un archivo de salida, lo movemos a Descargas
        for file in os.listdir(SCRIPTS_PATH):
            if file.lower().endswith((".xlsx", ".csv", ".pdf")):
                src_path = os.path.join(SCRIPTS_PATH, file)
                dest_path = os.path.join(OUTPUT_PATH, file)
                shutil.move(src_path, dest_path)
                print(f"📦 Archivo movido a Descargas: {dest_path}")

        if result.returncode == 0:
            return jsonify({
                "message": f"✅ {filename} ejecutado correctamente y enviado a Descargas",
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
# 🚀 EJECUCIÓN DEL SERVIDOR
# ==============================================
if __name__ == "__main__":
    print("🚀 Servidor Flask corriendo en: http://127.0.0.1:5000")
    print("📂 Carpeta de scripts:", SCRIPTS_PATH)
    print("📁 Carpeta de uploads:", UPLOADS_PATH)
    print("📤 Carpeta de Descargas:", OUTPUT_PATH)
    app.run(host="0.0.0.0", port=5000)
