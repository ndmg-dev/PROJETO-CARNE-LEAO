"""
Módulo de configuração central.
Todas as constantes e caminhos configuráveis ficam aqui.
"""
import os

# ──────────────────────────────────────────────
# Caminho base das pastas mensais no Google Drive
# ──────────────────────────────────────────────
DEFAULT_BASE_PATH = (
    r"C:\Users\User\Projetos\CARNE-LEAO-DADOS"
    r"\CARNE LEÃO DR. YURE 2024"
)

# ──────────────────────────────────────────────
# Extensões de arquivo suportadas
# ──────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# ──────────────────────────────────────────────
# Regex para detectar pastas mensais (01 - JANEIRO, etc.)
# ──────────────────────────────────────────────
MONTH_FOLDER_PATTERN = r"^(0[1-9]|1[0-2])\s*-\s*[A-ZÇÃ]+\s*$"

# ──────────────────────────────────────────────
# OpenAI API
# ──────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"

# ──────────────────────────────────────────────
# Google Drive API (produção/Docker — substitui o scan de filesystem local)
# ──────────────────────────────────────────────
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
USE_GOOGLE_DRIVE = bool(GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID)

# ──────────────────────────────────────────────
# CRM JWT (Bearer auth opcional para /api/*)
# ──────────────────────────────────────────────
CRM_JWT_SECRET = os.environ.get("CRM_JWT_SECRET", "")

# ──────────────────────────────────────────────
# Banco de dados SQLite (cache local)
# ──────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DB_PATH", os.path.join(PROJECT_DIR, "data.db"))

# ──────────────────────────────────────────────
# Padrões de Regex legados (fallback do parser)
# ──────────────────────────────────────────────
DATE_PATTERN = r"\b(0[1-9]|[12][0-9]|3[01])[-/\.](0[1-9]|1[0-2])[-/\.](19\d\d|20\d\d|\d{2})\b"
VALUE_PATTERN = r"(?:R\$\s*)?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}\b"
VALUE_KEYWORDS = [
    "valor pago", "valor total", "total pago", "valor do documento",
    "pagamento", "total", "liquido", "líquido", "importe", "valor",
    "pago", "r$"
]
