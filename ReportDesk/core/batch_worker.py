"""Background batch processing for ReportDesk (thread or multiprocessing)."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from db.repository import Repository

from .item_finalize import finalize_item
from .mp_worker import _init_pool, process_path_in_subprocess
from .pipeline import ProcessResult, ReportPipeline

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int, str], None]
DoneFn = Callable[[dict[str, int], str | None], None]


def _result_from_mp_payload(raw: dict) -> ProcessResult:
    scrape = json.loads(raw["scrape_json"]) if raw.get("scrape_json") else None
    return ProcessResult(
        raw["status"],
        Path(raw["path"]).name,
        report_type=raw.get("report_type"),
        report_no=raw.get("report_no"),
        decode_method=raw.get("decode_method"),
        scrape=scrape,
        error=raw.get("error"),
    )


class BatchWorker:
    def __init__(
        self,
        repo: Repository,
        settings: dict[str, str | None],
        on_log: LogFn,
        on_progress: ProgressFn,
        on_done: DoneFn,
        *,
        worker_count: int = 1,
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.on_log = on_log
        self.on_progress = on_progress
        self.on_done = on_done
        self.worker_count = max(1, min(10, worker_count))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def stop(self) -> None:
        self._stop.set()

    def start(self, paths: list[Path]) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        target = self._run_mp if self.worker_count > 1 else self._run_serial
        self._thread = threading.Thread(target=target, args=(paths,), daemon=True)
        self._thread.start()

    def _run_serial(self, paths: list[Path]) -> None:
        output_root = self.settings.get("output_root")
        if not output_root:
            self.on_done({"success": 0, "failed": 0, "skipped": len(paths)}, "未设置输出根目录")
            return

        out = Path(output_root)
        ocr_dir = self.settings.get("rapidocr_dir")
        paddle_dir = self.settings.get("paddleocr_dir")
        weights = self.settings.get("scanreport_weights_dir")
        pipeline = ReportPipeline(
            weights_folder=Path(weights) if weights else None,
            ocr_dir=Path(ocr_dir) if ocr_dir else None,
            paddleocr_dir=Path(paddle_dir) if paddle_dir else None,
            ocr_engine=self.settings.get("ocr_engine") or "auto",
            ocr_enabled=True,
        )

        job_id = self.repo.create_batch_job(len(paths), str(out))
        counts = {"success": 0, "failed": 0, "skipped": 0}
        total = len(paths)

        for i, path in enumerate(paths):
            if self._stop.is_set():
                self.on_log("已停止")
                break
            self._process_one(path, out, pipeline, job_id, counts, i, total)

        self.repo.finish_batch_job(
            job_id,
            success=counts["success"],
            failed=counts["failed"],
            skipped=counts["skipped"],
        )
        self.on_done(counts, None)

    def _run_mp(self, paths: list[Path]) -> None:
        output_root = self.settings.get("output_root")
        if not output_root:
            self.on_done({"success": 0, "failed": 0, "skipped": len(paths)}, "未设置输出根目录")
            return

        out = Path(output_root)
        job_id = self.repo.create_batch_job(len(paths), str(out))
        counts = {"success": 0, "failed": 0, "skipped": 0}
        total = len(paths)
        n_workers = self.worker_count
        self.on_log(f"多进程批处理：{n_workers} 个进程")

        completed = 0
        try:
            with ProcessPoolExecutor(
                max_workers=n_workers,
                initializer=_init_pool,
                initargs=(self.settings,),
            ) as pool:
                futures = {
                    pool.submit(process_path_in_subprocess, str(p.resolve())): p
                    for p in paths
                }
                for fut in as_completed(futures):
                    if self._stop.is_set():
                        pool.shutdown(wait=False, cancel_futures=True)
                        self.on_log("已停止")
                        break
                    path = futures[fut]
                    completed += 1
                    self.on_progress(completed, total, path.name)
                    item_id = self.repo.add_batch_item(job_id, str(path.resolve()))

                    if not path.is_file():
                        self.repo.update_batch_item(
                            item_id, status="skipped", error_message="file not found"
                        )
                        counts["skipped"] += 1
                        continue

                    try:
                        raw = fut.result()
                    except Exception as e:
                        self.repo.update_batch_item(
                            item_id, status="failed", error_message=str(e)
                        )
                        counts["failed"] += 1
                        self.on_log(f"FAIL {path.name}: {e}")
                        continue

                    result = _result_from_mp_payload(raw)
                    self._finalize_result(path, out, result, item_id, counts)

        except Exception as e:
            self.on_done(counts, str(e))
            return

        self.repo.finish_batch_job(
            job_id,
            success=counts["success"],
            failed=counts["failed"],
            skipped=counts["skipped"],
        )
        self.on_done(counts, None)

    def _process_one(
        self,
        path: Path,
        out: Path,
        pipeline: ReportPipeline,
        job_id: int,
        counts: dict[str, int],
        index: int,
        total: int,
    ) -> None:
        self.on_progress(index + 1, total, path.name)
        item_id = self.repo.add_batch_item(job_id, str(path.resolve()))

        if not path.is_file():
            self.repo.update_batch_item(item_id, status="skipped", error_message="file not found")
            counts["skipped"] += 1
            return

        result = pipeline.process_image(
            path,
            limis_base=self.settings.get("limis_base"),
            limis_user=self.settings.get("limis_user"),
            limis_password=self.settings.get("limis_password"),
            limis_auth_type=self.settings.get("limis_auth_type") or "1",
        )
        self._finalize_result(path, out, result, item_id, counts)

    def _finalize_result(
        self,
        path: Path,
        out: Path,
        result: ProcessResult,
        item_id: int,
        counts: dict[str, int],
    ) -> None:
        if result.status == "skipped":
            self.repo.update_batch_item(
                item_id, status="skipped", error_message=result.error
            )
            counts["skipped"] += 1
            self.on_log(f"SKIP {path.name}: {result.error}")
            return

        if not result.report_no:
            detail = result.error or "解码/爬取结果中无报告编号"
            self.repo.update_batch_item(item_id, status="failed", error_message=detail)
            counts["failed"] += 1
            self.on_log(
                f"FAIL {path.name}: 无报告编号"
                f"（{result.report_type or '?'}: {detail}）"
            )
            return

        ok, msg, dest, file_index = finalize_item(self.repo, out, path, result)
        if ok and dest:
            self.repo.update_batch_item(
                item_id,
                status="ok",
                report_no=result.report_no,
                file_index=file_index,
                stored_path=str(dest),
            )
            counts["success"] += 1
            self.on_log(f"OK {path.name} -> {msg}")
        else:
            self.repo.update_batch_item(item_id, status="failed", error_message=msg)
            counts["failed"] += 1
            self.on_log(f"FAIL {path.name}: {msg}")
