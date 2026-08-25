"""
Servidor Flask — Carnê-Leão 2024.
Expõe a interface web e as APIs REST/SSE para escanear pastas,
processar documentos com IA e exportar para Excel.
"""
import os
import sys
import io
import json
import time
import logging
from datetime import datetime

# Garante que src/ esteja no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import (
    Flask, request, jsonify, Response, send_file, send_from_directory
)

from src.config import (
    DEFAULT_BASE_PATH, OPENAI_API_KEY, OPENAI_MODEL, DB_PATH,
    USE_GOOGLE_DRIVE, CRM_JWT_SECRET,
)
from src.scanner import scan_folders
from src.parser import extract_description
from src.database import (
    init_db, upsert_document, get_documents,
    get_document, update_document, get_stats, clear_documents
)
from src.ai_extractor import extract_with_ai
from src.exporter import export_to_excel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder="static", static_url_path="/static")

# CORS habilitado apenas em /api/* para permitir chamadas do frontend do CRM
# a partir de outra origem (Bearer JWT, sem cookies de sessão envolvidos).
_CORS_ALLOWED_ORIGINS = [
    "https://crmmg.mendoncagalvao.com.br",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

try:
    from flask_cors import CORS
    CORS(app, resources={r"/api/*": {"origins": _CORS_ALLOWED_ORIGINS}},
         methods=["GET", "POST", "PUT", "DELETE"],
         allow_headers=["Authorization", "Content-Type"])
except ImportError:
    pass


# ─── Autenticação Bearer JWT (opcional, CRM_MG SSO) ─────────
# Se CRM_JWT_SECRET não estiver configurado, a checagem é desabilitada
# (comportamento padrão de desenvolvimento local, sem auth).

@app.before_request
def _require_crm_jwt():
    if not CRM_JWT_SECRET:
        return  # auth desabilitada (dev local)

    if not request.path.startswith("/api/"):
        return  # apenas /api/* exige token

    import jwt as pyjwt

    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return jsonify({"error": "Token de autenticação ausente."}), 401

    token = parts[1].strip()
    try:
        pyjwt.decode(token, CRM_JWT_SECRET, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado."}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({"error": "Token inválido."}), 401


# ─── Páginas ────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─── API: Escanear pastas ──────────────────────────────────

@app.route("/api/scan")
def api_scan():
    """Escaneia as pastas mensais e retorna um resumo."""
    base_path = request.args.get("path", DEFAULT_BASE_PATH)

    if not USE_GOOGLE_DRIVE:
        # Fallback para Vercel ou se o G:\ não existir (apenas modo local)
        if not os.path.exists(base_path):
            local_dataset = os.path.join(PROJECT_DIR, "DATASET")
            if os.path.exists(local_dataset):
                base_path = local_dataset

    try:
        folders = scan_folders(base_path)
        months = []
        for month_num, info in folders.items():
            months.append({
                "month_num": month_num,
                "name": info["folder_name"],
                "total_files": len(info["files"]),
            })
        return jsonify({"months": months, "base_path": base_path})
    except ValueError as e:
        # Tentar extrair do banco de dados como último recurso
        try:
            docs = get_documents(DB_PATH)
            unique_months = {}
            for doc in docs:
                if doc["month_num"] not in unique_months:
                    unique_months[doc["month_num"]] = {
                        "name": doc["month"],
                        "count": 0
                    }
                unique_months[doc["month_num"]]["count"] += 1
            
            months = []
            for m_num in sorted(unique_months.keys()):
                months.append({
                    "month_num": m_num,
                    "name": unique_months[m_num]["name"],
                    "total_files": unique_months[m_num]["count"]
                })
            return jsonify({"months": months, "base_path": "database_fallback"})
        except Exception:
            return jsonify({"error": str(e)}), 400


# ─── API: Processar documentos com IA (SSE) ────────────────

@app.route("/api/process")
def api_process():
    """
    Processa todos os documentos usando Gemini.
    Retorna um stream SSE (Server-Sent Events) para atualização em tempo real.
    """
    base_path = request.args.get("path", DEFAULT_BASE_PATH)
    api_key = request.args.get("api_key", OPENAI_API_KEY)
    force = request.args.get("force", "false") == "true"

    def generate():
        # 1) Escanear pastas
        try:
            folders = scan_folders(base_path)
        except ValueError as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        # 2) Contar total de arquivos
        total = sum(len(info["files"]) for info in folders.values())
        processed = 0

        yield _sse({"type": "start", "total": total})

        for month_num, info in folders.items():
            for file_entry in info["files"]:
                file_ref = file_entry["id"]
                filename = file_entry["name"]
                # Em modo local, "id" é o caminho completo no filesystem;
                # em modo Drive, é o ID do arquivo — usado como chave de
                # deduplicação no banco em ambos os casos.
                filepath = file_ref
                description = extract_description(filename)
                processed += 1

                # Emitir evento de progresso
                yield _sse({
                    "type": "processing",
                    "file": filename,
                    "month": info["folder_name"],
                    "current": processed,
                    "total": total,
                })

                # Verificar se já existe no banco (pula se já processado)
                if not force:
                    existing = _find_by_filepath(filepath)
                    if existing and existing["status"] != "pending":
                        yield _sse({
                            "type": "skipped",
                            "file": filename,
                            "current": processed,
                            "total": total,
                        })
                        continue

                # Chamar OpenAI (com retry básico)
                result = None
                max_retries = 2
                for attempt in range(max_retries):
                    result = extract_with_ai(file_ref, filename, api_key, OPENAI_MODEL)

                    # Se der erro, esperar um pouco e tentar de novo
                    if result.get("error"):
                        wait_time = 5 * (attempt + 1)
                        yield _sse({
                            "type": "processing",
                            "file": f"{filename} (erro, aguardando {wait_time}s...)",
                            "month": info["folder_name"],
                            "current": processed,
                            "total": total,
                        })
                        time.sleep(wait_time)
                        continue
                    break  # Sucesso ou erro final

                date_str = result.get("data_pagamento")
                valor = result.get("valor")
                confidence = result.get("confianca", "baixa")
                tipo = result.get("tipo_documento", "")

                # Determinar status
                if date_str and valor and confidence in ("alta", "media"):
                    status = "ok"
                elif date_str or valor:
                    status = "review"
                else:
                    status = "error"

                doc = {
                    "month": info["folder_name"],
                    "month_num": month_num,
                    "filename": filename,
                    "filepath": filepath,
                    "description": description,
                    "date": date_str,
                    "value": valor,
                    "status": status,
                    "confidence": confidence,
                    "observation": tipo,
                    "processed_at": datetime.now().isoformat(),
                }

                upsert_document(DB_PATH, doc)

                yield _sse({
                    "type": "processed",
                    "document": doc,
                    "current": processed,
                    "total": total,
                })

                # Pequena pausa para não afogar a rede (0.5s)
                time.sleep(0.5)

        yield _sse({"type": "done", "total": total})

    return Response(generate(), mimetype="text/event-stream")


# ─── API: Listar documentos ────────────────────────────────

@app.route("/api/documents")
def api_documents():
    month = request.args.get("month")
    status = request.args.get("status")
    docs = get_documents(DB_PATH, month=month, status=status)
    return jsonify({"documents": docs})


# ─── API: Detalhe de um documento ──────────────────────────

@app.route("/api/document/<int:doc_id>")
def api_document(doc_id):
    doc = get_document(DB_PATH, doc_id)
    if doc:
        return jsonify({"document": doc})
    return jsonify({"error": "Documento não encontrado"}), 404


# ─── API: Editar documento ─────────────────────────────────

@app.route("/api/document/<int:doc_id>", methods=["PUT"])
def api_update_document(doc_id):
    data = request.json
    update_document(
        DB_PATH, doc_id,
        date=data.get("date"),
        value=data.get("value"),
    )
    doc = get_document(DB_PATH, doc_id)
    return jsonify({"success": True, "document": doc})


# ─── API: Estatísticas ─────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    stats = get_stats(DB_PATH)
    return jsonify(stats)


# ─── API: Exportar Excel ───────────────────────────────────

@app.route("/api/export", methods=["GET", "POST"])
def api_export():
    if request.method == "POST":
        data = request.get_json()
        if data and "documents" in data:
            docs = data["documents"]
        else:
            docs = get_documents(DB_PATH)
    else:
        docs = get_documents(DB_PATH)
    successful = []
    pending = []

    for doc in docs:
        if doc["status"] in ("ok", "review"):
            # Converter string de data para objeto date
            date_obj = ""
            if doc["date"]:
                try:
                    date_obj = datetime.strptime(doc["date"], "%d/%m/%Y").date()
                except ValueError:
                    date_obj = doc["date"]

            status_label = "OK"
            if doc["status"] == "review":
                parts = []
                if not doc["date"]:
                    parts.append("Data Ausente")
                if not doc["value"]:
                    parts.append("Valor Ausente")
                elif doc.get("confidence") == "baixa":
                    parts.append("Baixa Confiança")
                status_label = " | ".join(parts) if parts else "Revisão"

            successful.append({
                "month": doc["month"],
                "date": date_obj,
                "description": doc["description"],
                "value": doc["value"] if doc["value"] else "",
                "filename": doc["filename"],
                "filepath": doc["filepath"],
                "status": status_label,
            })
        else:
            pending.append({
                "month": doc["month"],
                "filename": doc["filename"],
                "filepath": doc["filepath"],
                "status": doc["status"].title(),
                "motivo": doc.get("observation", "Dados não encontrados"),
            })

    try:
        output = io.BytesIO()
        export_to_excel(successful, pending, output)
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name="despesas_carne_leao_2024.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API: Preview do documento ─────────────────────────────

@app.route("/api/preview/<int:doc_id>")
def api_preview(doc_id):
    """Serve uma imagem de preview do documento (converte PDF para PNG)."""
    doc = get_document(DB_PATH, doc_id)
    if not doc:
        return jsonify({"error": "Documento não encontrado"}), 404

    filepath = doc["filepath"]
    ext = os.path.splitext(doc["filename"])[1].lower()

    if USE_GOOGLE_DRIVE:
        # Em modo Drive, "filepath" guarda o ID do arquivo no Drive.
        from src.drive_client import get_drive_service, download_file
        try:
            service = get_drive_service()
            buf = download_file(service, filepath)
        except Exception as e:
            return jsonify({"error": f"Falha ao baixar do Google Drive: {e}"}), 500

        if ext in {".jpg", ".jpeg", ".png"}:
            return send_file(buf, mimetype="image/jpeg" if ext != ".png" else "image/png")

        elif ext == ".pdf":
            import fitz
            try:
                pdf_doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
                page = pdf_doc[0]
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pdf_doc.close()

                out_buf = io.BytesIO()
                img.save(out_buf, format="PNG")
                out_buf.seek(0)
                return send_file(out_buf, mimetype="image/png")
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        return jsonify({"error": "Tipo de arquivo não suportado para preview"}), 400

    # Modo local (fallback de desenvolvimento)
    # Se estiver rodando na Vercel (Linux) ou não encontrar no G:\,
    # tenta buscar na pasta "DATASET" local do projeto.
    if not os.path.exists(filepath):
        local_dataset = os.path.join(PROJECT_DIR, "DATASET", doc["month"], doc["filename"])
        if os.path.exists(local_dataset):
            filepath = local_dataset
        else:
            return jsonify({"error": "Arquivo não encontrado"}), 404

    if ext in {".jpg", ".jpeg", ".png"}:
        return send_file(filepath)

    elif ext == ".pdf":
        import fitz
        try:
            pdf_doc = fitz.open(filepath)
            page = pdf_doc[0]
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pdf_doc.close()

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return send_file(buf, mimetype="image/png")
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Tipo de arquivo não suportado para preview"}), 400


# ─── Helpers ────────────────────────────────────────────────

def _sse(data):
    """Formata um evento SSE."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _find_by_filepath(filepath):
    """Busca um documento pelo caminho no banco."""
    from src.database import get_connection
    conn = get_connection(DB_PATH)
    row = conn.execute(
        "SELECT * FROM documents WHERE filepath = ?", (filepath,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Pillow import (usado no preview de PDFs) ──────────────
from PIL import Image


# ─── Inicialização ─────────────────────────────────────────
# Executado tanto via `python app.py` (dev) quanto via `gunicorn app:app`
# (produção), garantindo que o schema exista antes do primeiro request.
init_db(DB_PATH)

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Carne-Leao 2024 - Interface Web")
    print("  Abra no navegador: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000, threaded=True)
