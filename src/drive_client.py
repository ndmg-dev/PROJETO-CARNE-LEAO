"""
Cliente do Google Drive API v3.
Substitui o acesso via filesystem local (pasta sincronizada do Google Drive)
por chamadas diretas à API, usando uma Service Account — necessário porque
em produção (Docker/Coolify em Linux) não há acesso ao disco sincronizado
do usuário.
"""
import io
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from . import config

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

_service = None


def get_drive_service():
    """
    Retorna uma instância autenticada (e cacheada) do cliente Drive v3.
    Levanta RuntimeError com mensagem clara se as credenciais não estiverem
    configuradas.
    """
    global _service
    if _service is not None:
        return _service

    if not config.GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON não configurado. "
            "Defina a variável de ambiente com o JSON da Service Account "
            "do Google Cloud para habilitar o acesso ao Google Drive."
        )

    try:
        info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"GOOGLE_SERVICE_ACCOUNT_JSON não é um JSON válido: {e}"
        )

    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    _service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _service


def list_subfolders(service, parent_folder_id):
    """Lista as subpastas diretas de parent_folder_id (id, name)."""
    folders = []
    page_token = None
    query = (
        f"'{parent_folder_id}' in parents "
        "and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
        ).execute()
        folders.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return folders


def list_files_in_folder(service, folder_id):
    """Lista os arquivos (não-pastas) dentro de folder_id (id, name, mimeType)."""
    files = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed=false"
    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return files


def download_file(service, file_id):
    """Baixa o conteúdo de um arquivo do Drive para um buffer BytesIO."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    buf.seek(0)
    return buf
