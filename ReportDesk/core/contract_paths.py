"""合同表驱动的输出目录上级文件夹。"""

from __future__ import annotations

from typing import Any, Callable

FOLDER_PARENT_NONE = "无"
FOLDER_PARENT_MANAGER = "负责人"
FOLDER_PARENT_HANDLER = "经办人"
VALID_FOLDER_PARENTS = (FOLDER_PARENT_NONE, FOLDER_PARENT_MANAGER, FOLDER_PARENT_HANDLER)


def resolve_parent_folder_name(
    project_name: str | None,
    folder_parent_mode: str | None,
    lookup: Callable[[str], dict[str, Any] | None],
) -> str | None:
    """
    根据设置与合同表返回工程名称上一级目录名。
    工程名称须精确匹配；无匹配或未配置则返回 None。
    """
    mode = (folder_parent_mode or FOLDER_PARENT_NONE).strip()
    if mode == FOLDER_PARENT_NONE or not project_name:
        return None
    row = lookup(str(project_name).strip())
    if not row:
        return None
    if mode == FOLDER_PARENT_MANAGER:
        name = (row.get("manager") or "").strip()
    elif mode == FOLDER_PARENT_HANDLER:
        name = (row.get("handler") or "").strip()
    else:
        return None
    return name or None
