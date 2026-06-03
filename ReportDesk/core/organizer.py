"""Copy report images into 报告/工程名/[标段/]编号-N.ext layout."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from typing import Any, Callable

from .constants import NO_SECTION, PENDING_VERIFY, UNKNOWN_PROJECT
from .contract_paths import resolve_parent_folder_name

_INVALID_PATH = re.compile(r'[\\/:*?"<>|]')
_MAX_COMPONENT_LEN = 80


def sanitize_path_component(name: str | None, *, fallback: str = "未命名") -> str:
    if not name or not str(name).strip():
        return fallback
    s = str(name).strip()
    if s in ("-", "—", "－"):
        return fallback
    s = _INVALID_PATH.sub("_", s)
    s = s.strip(" .")
    if not s:
        return fallback
    if len(s) > _MAX_COMPONENT_LEN:
        s = s[:_MAX_COMPONENT_LEN].rstrip()
    return s


def is_real_section(section_folder: str | None) -> bool:
    """有有效标段名时才增加一级子目录；院网/内网或无标段则扁平放在工程目录下。"""
    if section_folder is None:
        return False
    s = str(section_folder).strip()
    if not s or s in ("-", "—", "－", NO_SECTION):
        return False
    return True


def build_target_dir(
    output_root: Path,
    project_name: str | None,
    section_folder: str | None,
    *,
    pending: bool = False,
    folder_parent_mode: str | None = None,
    contract_lookup: Callable[[str], dict[str, Any] | None] | None = None,
) -> Path:
    root = output_root / "报告"
    if pending:
        if is_real_section(section_folder):
            return root / PENDING_VERIFY / sanitize_path_component(
                section_folder, fallback="未命名标段"
            )
        return root / PENDING_VERIFY

    proj = sanitize_path_component(project_name, fallback=UNKNOWN_PROJECT)
    base = root
    if contract_lookup and project_name:
        parent_name = resolve_parent_folder_name(
            project_name, folder_parent_mode, contract_lookup
        )
        if parent_name:
            base = root / sanitize_path_component(parent_name, fallback="未分类")

    if is_real_section(section_folder):
        section = sanitize_path_component(section_folder, fallback="未命名标段")
        return base / proj / section
    return base / proj


def build_stored_filename(report_no: str, file_index: int, source: Path) -> str:
    ext = source.suffix.lower() if source.suffix else ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".bmp"):
        ext = ".jpg"
    return f"{report_no}-{file_index}{ext}"


def copy_report_file(
    source: Path,
    output_root: Path,
    report_no: str,
    file_index: int,
    project_name: str | None,
    section_folder: str | None,
    *,
    pending: bool = False,
    folder_parent_mode: str | None = None,
    contract_lookup: Callable[[str], dict[str, Any] | None] | None = None,
) -> Path:
    dest_dir = build_target_dir(
        output_root,
        project_name,
        section_folder,
        pending=pending,
        folder_parent_mode=folder_parent_mode,
        contract_lookup=contract_lookup,
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = build_stored_filename(report_no, file_index, source)
    dest = dest_dir / filename
    shutil.copy2(source, dest)
    return dest.resolve()


# Aliases for tests
build_dest_dir = build_target_dir
dest_filename = build_stored_filename
SECTION_NONE = NO_SECTION
