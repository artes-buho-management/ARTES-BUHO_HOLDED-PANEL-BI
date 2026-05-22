from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from reporting.drive_manager import (
    ANNUAL_FOLDER_NAME,
    MONTHLY_FOLDER_NAME,
    REPORTS_FOLDER_NAME,
    WEEKLY_FOLDER_NAME,
    ensure_standard_report_structure,
)


@dataclass
class FakeAdapter:
    folders: Dict[str, Dict[str, str]] = field(default_factory=dict)
    counter: int = 1

    def _key(self, parent_id: str, name: str) -> str:
        return f"{parent_id}::{name}"

    def find_folder(self, name: str, parent_id: str) -> Optional[str]:
        return self.folders.get(self._key(parent_id, name), {}).get("id")

    def create_folder(self, name: str, parent_id: str) -> str:
        key = self._key(parent_id, name)
        folder_id = f"F{self.counter}"
        self.counter += 1
        self.folders[key] = {"id": folder_id, "name": name, "parent_id": parent_id}
        return folder_id


def test_create_full_structure_when_missing():
    fake = FakeAdapter()
    tree = ensure_standard_report_structure(fake, "PARENT")
    assert tree.parent_folder_id == "PARENT"
    assert tree.informes_id
    assert tree.semanal_id
    assert tree.mensual_id
    assert tree.anual_id


def test_reuse_existing_structure():
    fake = FakeAdapter()
    informes = fake.create_folder(REPORTS_FOLDER_NAME, "PARENT")
    semanal = fake.create_folder(WEEKLY_FOLDER_NAME, informes)
    mensual = fake.create_folder(MONTHLY_FOLDER_NAME, informes)
    anual = fake.create_folder(ANNUAL_FOLDER_NAME, informes)

    tree = ensure_standard_report_structure(fake, "PARENT")
    assert tree.informes_id == informes
    assert tree.semanal_id == semanal
    assert tree.mensual_id == mensual
    assert tree.anual_id == anual

