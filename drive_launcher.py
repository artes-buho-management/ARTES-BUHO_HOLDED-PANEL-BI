from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import Settings, get_service_account_info, get_settings


DOC_MIME = "application/vnd.google-apps.document"


def main() -> None:
    settings = get_settings()
    title = f"ABRIR PANEL - {settings.panel_name}".strip()
    body = _build_launcher_content(settings)

    try:
        doc_url = create_or_update_launcher_doc(settings, title, body)
        print(f"OK: documento lanzador creado/actualizado -> {doc_url}")
    except Exception as exc:
        fallback_path = Path("drive_launcher_fallback.md")
        fallback_path.write_text(body, encoding="utf-8")
        print("No fue posible crear el documento automaticamente en Drive.")
        print(f"Motivo: {exc}")
        print(f"Fallback generado en: {fallback_path.resolve()}")


def create_or_update_launcher_doc(settings: Settings, title: str, body: str) -> str:
    info = get_service_account_info(settings)
    if not info:
        raise RuntimeError(
            "Faltan credenciales Google API. Define GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_APPLICATION_CREDENTIALS."
        )

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)

    if not settings.google_sheet_id:
        raise RuntimeError("Falta GOOGLE_SHEET_ID.")
    if not settings.streamlit_public_url:
        raise RuntimeError("Falta STREAMLIT_PUBLIC_URL.")

    sheet_meta = drive.files().get(
        fileId=settings.google_sheet_id, fields="id,name,parents"
    ).execute()
    parent_folder_id = settings.google_drive_folder_id or (sheet_meta.get("parents") or [None])[0]
    if not parent_folder_id:
        raise RuntimeError(
            "No se detecto carpeta padre de la hoja. Define GOOGLE_DRIVE_FOLDER_ID."
        )

    doc_id = _find_existing_doc(drive, title, parent_folder_id)
    if not doc_id:
        doc_id = _create_doc(drive, title, parent_folder_id)

    _replace_doc_body(docs, doc_id, body)
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def _find_existing_doc(drive, title: str, folder_id: str) -> Optional[str]:
    safe_title = title.replace("'", "\\'")
    query = (
        f"name = '{safe_title}' and "
        f"'{folder_id}' in parents and "
        f"mimeType = '{DOC_MIME}' and trashed = false"
    )
    result = (
        drive.files()
        .list(q=query, fields="files(id,name)", pageSize=1, includeItemsFromAllDrives=True, supportsAllDrives=True)
        .execute()
    )
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _create_doc(drive, title: str, folder_id: str) -> str:
    payload: Dict[str, object] = {"name": title, "mimeType": DOC_MIME, "parents": [folder_id]}
    result = (
        drive.files()
        .create(body=payload, fields="id", supportsAllDrives=True)
        .execute()
    )
    return result["id"]


def _replace_doc_body(docs, doc_id: str, text: str) -> None:
    doc = docs.documents().get(documentId=doc_id).execute()
    end_index = (
        doc.get("body", {})
        .get("content", [{}])[-1]
        .get("endIndex", 1)
    )

    requests = []
    if end_index and end_index > 1:
        requests.append(
            {
                "deleteContentRange": {
                    "range": {"startIndex": 1, "endIndex": end_index - 1}
                }
            }
        )
    requests.append({"insertText": {"location": {"index": 1}, "text": text}})

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()


def _build_launcher_content(settings: Settings) -> str:
    return (
        f"# ABRIR PANEL - {settings.panel_name}\n\n"
        f"## Descripcion\n"
        f"{settings.panel_description}\n\n"
        f"## Acceso al panel\n"
        f"{settings.streamlit_public_url}\n\n"
        "## Uso rapido\n"
        "1. Abre el enlace del panel.\n"
        "2. Filtra por fecha y dimensiones en el lateral.\n"
        "3. Revisa KPIs, insights y tabla de detalle.\n"
        "4. Comparte este mismo documento con quien deba acceder.\n"
    )


if __name__ == "__main__":
    main()
