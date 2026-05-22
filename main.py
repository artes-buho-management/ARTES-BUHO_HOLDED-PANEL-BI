from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from config import get_settings
from reporting.drive_manager import DriveManager
from reporting.generator import generate_report

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sistema de informes corporativos automatizados (Artes Buho)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generar informe PDF.")
    generate_sub = generate.add_subparsers(dest="report_type", required=True)

    for report_type in ("weekly", "monthly", "annual"):
        p = generate_sub.add_parser(report_type, help=f"Generar informe {report_type}.")
        p.add_argument(
            "--run-datetime",
            default="",
            help="Fecha/hora de ejecucion. Formato: YYYY-MM-DD HH:MM",
        )
        p.add_argument(
            "--sheet-name",
            default="",
            help="Pestana concreta a usar. Si se omite, seleccion automatica.",
        )
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Genera localmente y no sube a Drive.",
        )
        p.add_argument(
            "--overwrite",
            action="store_true",
            help="Sobrescribe en Drive si ya existe el PDF del mismo nombre.",
        )

    setup_drive = subparsers.add_parser(
        "setup-drive",
        help="Crea o reutiliza Informes/InformeSemanal|Mensual|Anual en Drive.",
    )
    setup_drive.add_argument(
        "--sheet-id",
        default="",
        help="Opcional. Si se omite, usa GOOGLE_SHEET_ID.",
    )
    return parser


def main() -> int:
    if load_dotenv:
        load_dotenv()

    parser = _build_parser()
    args = parser.parse_args()

    settings = get_settings()
    if args.command == "setup-drive":
        manager = DriveManager.from_settings(settings)
        folders = manager.ensure_report_structure(
            sheet_id=args.sheet_id or settings.google_sheet_id,
            forced_parent_id=settings.google_drive_folder_id,
        )
        print(
            json.dumps(
                {
                    "parent_folder_id": folders.parent_folder_id,
                    "Informes": folders.informes_id,
                    "InformeSemanal": folders.semanal_id,
                    "InformeMensual": folders.mensual_id,
                    "InformeAnual": folders.anual_id,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    result = generate_report(
        report_type=args.report_type,
        settings=settings,
        run_datetime_str=args.run_datetime,
        sheet_name=args.sheet_name,
        overwrite=bool(args.overwrite),
        dry_run=bool(args.dry_run),
    )

    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
