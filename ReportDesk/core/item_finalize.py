"""单条报告：归一化、入库、复制到输出目录。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from db.repository import Repository

from .constants import PENDING_VERIFY
from .contract_paths import FOLDER_PARENT_NONE, resolve_parent_folder_name
from .normalize import normalize_from_scrape, normalize_partial, normalize_report_no
from .organizer import copy_report_file, sanitize_path_component
from .pipeline import ProcessResult


def apply_manual_fields(bundle: dict[str, Any], fields: dict[str, str]) -> None:
    row = bundle["report"]
    if fields.get("project_name"):
        row["project_name"] = fields["project_name"]
    if fields.get("section"):
        from .normalize import section_folder_for_association

        row["project_section_extra"] = fields["section"]
        if row.get("source_channel") == "association":
            row["section_folder"] = section_folder_for_association(fields["section"])
    if fields.get("report_date"):
        row["report_date"] = fields["report_date"]
    if fields.get("order_no"):
        row["order_no"] = fields["order_no"]
    if fields.get("anti_fake_code"):
        row["anti_fake_code"] = fields["anti_fake_code"]
    if fields.get("sample_name") and bundle.get("samples"):
        bundle["samples"][0]["sample_name"] = fields["sample_name"]
    elif fields.get("sample_name"):
        bundle["samples"] = [{"sample_name": fields["sample_name"]}]


def finalize_item(
    repo: Repository,
    output_root: Path,
    path: Path,
    result: ProcessResult,
    *,
    manual_fields: dict[str, str] | None = None,
    force_partial: bool = False,
) -> tuple[bool, str, Path | None, int | None]:
    """返回 (成功, 消息, 目标路径, file_index)。"""
    report_no = normalize_report_no(result.report_no or (manual_fields or {}).get("report_no"))
    if not report_no:
        return False, "无报告编号", None, None

    channel = result.report_type or "unknown"
    decode_method = result.decode_method or "unknown"

    try:
        if not force_partial and result.status == "success" and result.scrape:
            bundle = normalize_from_scrape(
                result.scrape,
                report_no=report_no,
                source_channel=channel,
                decode_method=decode_method,
                source_image=path.name,
            )
        else:
            bundle = normalize_partial(
                report_no,
                channel,
                decode_method,
                error=result.error,
            )
        if manual_fields:
            apply_manual_fields(bundle, manual_fields)

        repo.save_normalized_bundle(bundle)
        report_row = bundle["report"]
        pending = (
            force_partial
            or report_row.get("scrape_status") == "partial"
            or not report_row.get("project_name")
        )
        folder_parent = repo.get_setting("organize_folder_parent") or FOLDER_PARENT_NONE
        file_index = repo.allocate_file_index(report_no)
        dest = copy_report_file(
            path,
            output_root,
            report_no,
            file_index,
            report_row.get("project_name"),
            report_row.get("section_folder"),
            pending=pending,
            folder_parent_mode=folder_parent,
            contract_lookup=repo.lookup_project_contract,
        )
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        repo.insert_report_file(
            report_no,
            file_index,
            str(path.resolve()),
            str(dest),
            path.name,
            file_hash,
        )
        proj_dir = sanitize_path_component(
            report_row.get("project_name"), fallback=PENDING_VERIFY
        )
        parent_name = resolve_parent_folder_name(
            report_row.get("project_name"),
            folder_parent,
            repo.lookup_project_contract,
        )
        if parent_name:
            parent_seg = sanitize_path_component(parent_name, fallback="未分类")
            proj_dir = f"{parent_seg}/{proj_dir}"
        sect_dir = (
            sanitize_path_component(report_row["section_folder"])
            if report_row.get("section_folder")
            else ""
        )
        report_row["organize_project_dir"] = proj_dir
        report_row["organize_section_dir"] = sect_dir
        repo.upsert_report(report_row)
        return True, f"{report_no}-{file_index}", dest, file_index
    except Exception as e:
        return False, str(e), None, None
