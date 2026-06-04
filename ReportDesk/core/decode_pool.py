"""单 worker 进程池：复用已加载的 QReader 模型。"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor
from typing import Any

_executor: ProcessPoolExecutor | None = None
_settings_key: tuple[tuple[str, str | None], ...] | None = None


def get_decode_executor(settings: dict[str, str | None]) -> ProcessPoolExecutor:
    global _executor, _settings_key
    key = tuple(sorted((k, settings.get(k)) for k in (
        "rapidocr_dir",
        "scanreport_weights_dir",
        "limis_base",
        "limis_user",
        "limis_password",
        "limis_auth_type",
    )))
    if _executor is not None and _settings_key == key:
        return _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
    from .mp_worker import _init_pool

    _settings_key = key
    _executor = ProcessPoolExecutor(
        max_workers=1,
        initializer=_init_pool,
        initargs=(settings,),
    )
    return _executor


def submit_decode(
    settings: dict[str, str | None],
    path_str: str,
) -> Future:
    from .decode_worker import decode_path_in_subprocess

    return get_decode_executor(settings).submit(decode_path_in_subprocess, path_str)


def shutdown_decode_pool() -> None:
    global _executor, _settings_key
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
    _settings_key = None
