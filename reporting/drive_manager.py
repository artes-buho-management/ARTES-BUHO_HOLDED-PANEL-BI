from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload

from config import Settings, get_service_account_info


FOLDER_MIME = "application/vnd.google-apps.folder"
REPORTS_FOLDER_NAME = "Informes"
WEEKLY_FOLDER_NAME = "InformeSemanal"
MONTHLY_FOLDER_NAME = "InformeMensual"
ANNUAL_FOLDER_NAME = "InformeAnual"


@dataclass(frozen=True)
class DriveFolders:
    parent_folder_id: str
    informes_id: str
    semanal_id: str
    mensual_id: str
    anual_id: str

    def target_folder(self, report_type: str) -> str:
        if report_type == "weekly":
            return self.semanal_id
        if report_type == "monthly":
            return self.mensual_id
        if report_type == "annual":
            return self.anual_id
        raise ValueError(f"Tipo no soportado: {report_type}")


@dataclass(frozen=True)
class UploadResult:
    status: str
    file_id: Optional[str]
    web_view_link: Optional[str]
    message: str


class FolderAdapter(Protocol):
    def find_folder(self, name: str, parent_id: str) -> Optional[str]:
        ...

    def create_folder(self, name: str, parent_id: str) -> str:
        ...


def ensure_standard_report_structure(
    adapter: FolderAdapter, parent_folder_id: str
) -> DriveFolders:
    informes = adapter.find_folder(REPORTS_FOLDER_NAME, parent_folder_id)
    if not informes:
        informes = adapter.create_folder(REPORTS_FOLDER_NAME, parent_folder_id)

    semanal = adapter.find_folder(WEEKLY_FOLDER_NAME, informes)
    if not semanal:
        semanal = adapter.create_folder(WEEKLY_FOLDER_NAME, informes)

    mensual = adapter.find_folder(MONTHLY_FOLDER_NAME, informes)
    if not mensual:
        mensual = adapter.create_folder(MONTHLY_FOLDER_NAME, informes)

    anual = adapter.find_folder(ANNUAL_FOLDER_NAME, informes)
    if not anual:
        anual = adapter.create_folder(ANNUAL_FOLDER_NAME, informes)

    return DriveFolders(
        parent_folder_id=parent_folder_id,
        informes_id=informes,
        semanal_id=semanal,
        mensual_id=mensual,
        anual_id=anual,
    )


class DriveManager(FolderAdapter):
    def __init__(self, drive_service: Resource):
        self.drive = drive_service

    @classmethod
    def from_settings(cls, settings: Settings) -> "DriveManager":
        info = get_service_account_info(settings)
        if not info:
            raise RuntimeError(
                "No hay credenciales Google API para Drive. Define GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_APPLICATION_CREDENTIALS."
            )
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        return cls(drive)

    def find_folder(self, name: str, parent_id: str) -> Optional[str]:
        safe_name = name.replace("'", "\\'")
        query = (
            f"name = '{safe_name}' and "
            f"'{parent_id}' in parents and "
            f"mimeType = '{FOLDER_MIME}' and trashed = false"
        )
        resp = (
            self.drive.files()
            .list(
                q=query,
                fields="files(id,name)",
                pageSize=1,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def create_folder(self, name: str, parent_id: str) -> str:
        body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        created = (
            self.drive.files()
            .create(body=body, fields="id", supportsAllDrives=True)
            .execute()
        )
        return created["id"]

    def resolve_sheet_parent_folder(
        self, sheet_id: str, forced_parent_id: str = ""
    ) -> str:
        if forced_parent_id:
            return forced_parent_id

        meta = (
            self.drive.files()
            .get(
                fileId=sheet_id,
                fields="id,name,parents,driveId",
                supportsAllDrives=True,
            )
            .execute()
        )
        parents = meta.get("parents") or []
        if parents:
            return parents[0]

        drive_id = meta.get("driveId")
        if drive_id:
            return drive_id

        raise RuntimeError(
            "No se detecto carpeta padre de la hoja. Define GOOGLE_DRIVE_FOLDER_ID."
        )

    def ensure_report_structure(
        self, sheet_id: str, forced_parent_id: str = ""
    ) -> DriveFolders:
        parent_id = self.resolve_sheet_parent_folder(sheet_id, forced_parent_id)
        return ensure_standard_report_structure(self, parent_id)

    def upload_pdf(
        self,
        local_pdf_path: str,
        target_folder_id: str,
        filename: str,
        overwrite: bool = False,
    ) -> UploadResult:
        existing = self._find_file(filename, target_folder_id)
        media = MediaFileUpload(local_pdf_path, mimetype="application/pdf", resumable=False)

        if existing and not overwrite:
            file_id = existing["id"]
            return UploadResult(
                status="skipped",
                file_id=file_id,
                web_view_link=f"https://drive.google.com/file/d/{file_id}/view",
                message="El archivo ya existe. Se omite por politica por defecto (skip).",
            )

        if existing and overwrite:
            file_id = existing["id"]
            updated = (
                self.drive.files()
                .update(
                    fileId=file_id,
                    media_body=media,
                    fields="id,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
            return UploadResult(
                status="overwritten",
                file_id=updated.get("id"),
                web_view_link=updated.get("webViewLink"),
                message="Archivo existente actualizado por overwrite.",
            )

        body = {"name": filename, "parents": [target_folder_id]}
        created = (
            self.drive.files()
            .create(
                body=body,
                media_body=media,
                fields="id,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        return UploadResult(
            status="uploaded",
            file_id=created.get("id"),
            web_view_link=created.get("webViewLink"),
            message="Archivo PDF subido correctamente.",
        )

    def _find_file(self, filename: str, parent_id: str) -> Optional[dict]:
        safe_name = filename.replace("'", "\\'")
        query = (
            f"name = '{safe_name}' and "
            f"'{parent_id}' in parents and "
            "mimeType = 'application/pdf' and trashed = false"
        )
        resp = (
            self.drive.files()
            .list(
                q=query,
                fields="files(id,name,webViewLink)",
                pageSize=1,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        files = resp.get("files", [])
        return files[0] if files else None
