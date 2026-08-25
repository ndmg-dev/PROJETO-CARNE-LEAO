import os
import re
from . import config
from .config import MONTH_FOLDER_PATTERN, SUPPORTED_EXTENSIONS


def is_valid_month_folder(folder_name):
    """Checks if a folder name matches the expected monthly pattern."""
    return bool(re.match(MONTH_FOLDER_PATTERN, folder_name, re.IGNORECASE))


def _scan_folders_drive(folder_id):
    """
    Escaneia as subpastas mensais de um diretório raiz no Google Drive.
    Cada entrada em "files" é um dict {"id": drive_file_id, "name": filename}.
    """
    from . import drive_client

    service = drive_client.get_drive_service()

    results = {}
    subfolders = drive_client.list_subfolders(service, folder_id)

    if not subfolders:
        raise ValueError(
            "Nenhuma subpasta encontrada na pasta configurada do Google Drive "
            f"(GOOGLE_DRIVE_FOLDER_ID={folder_id}). Verifique se o ID está "
            "correto e se a Service Account tem acesso à pasta."
        )

    for folder in subfolders:
        name = folder["name"]
        if not is_valid_month_folder(name):
            continue

        match = re.search(r"^(0[1-9]|1[0-2])", name)
        if not match:
            continue
        month_num = match.group(1)

        files = []
        for f in drive_client.list_files_in_folder(service, folder["id"]):
            ext = os.path.splitext(f["name"])[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                files.append({"id": f["id"], "name": f["name"]})

        results[month_num] = {
            "folder_name": name,
            # Reaproveitamos o id da pasta no Drive como "folder_path"
            # (não existe caminho de filesystem em modo Drive).
            "folder_path": folder["id"],
            "files": files,
        }

    return dict(sorted(results.items()))


def _scan_folders_local(base_path):
    """
    Escaneia o filesystem local (modo de desenvolvimento/fallback).
    Cada entrada em "files" é um dict {"id": full_local_path, "name": filename}
    para manter a mesma forma usada pelo modo Drive.
    """
    if not os.path.exists(base_path):
        raise ValueError(
            "Base path does not exist or is not accessible. Please check if "
            f"the drive is mounted and the path is correct:\n{base_path}"
        )

    results = {}

    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path) and is_valid_month_folder(item):
            match = re.search(r"^(0[1-9]|1[0-2])", item)
            if match:
                month_num = match.group(1)

                files = []
                for root, _, filenames in os.walk(item_path):
                    for filename in filenames:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            files.append({
                                "id": os.path.join(root, filename),
                                "name": filename,
                            })

                results[month_num] = {
                    "folder_name": item,
                    "folder_path": item_path,
                    "files": files,
                }

    return dict(sorted(results.items()))


def scan_folders(base_path=None, folder_id=None):
    """
    Escaneia as pastas mensais e retorna:
    {month_num: {"folder_name":..., "folder_path":..., "files": [{"id":..., "name":...}, ...]}}
    sorted by month_num.

    Em modo Google Drive (config.USE_GOOGLE_DRIVE), base_path é ignorado e o
    escaneamento é feito via API a partir de folder_id (ou
    config.GOOGLE_DRIVE_FOLDER_ID por padrão). Caso contrário, faz fallback
    para o escaneamento local via filesystem (comportamento original).
    """
    if config.USE_GOOGLE_DRIVE:
        target_folder_id = folder_id or config.GOOGLE_DRIVE_FOLDER_ID
        return _scan_folders_drive(target_folder_id)

    return _scan_folders_local(base_path)
