"""整理页：待处理 | 预览 | 字段；支持逐个整理流水线。"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from db.repository import Repository

from core.batch_worker import BatchWorker
from core.decode_pool import submit_decode
from core.decode_worker import dict_to_decode_outcome
from gui.image_preview import show_image_on_label
from core.field_map import (
    FIELD_KEYS,
    OCR_FIELD_KEY,
    UI_ENTRY_KEYS,
    UI_FIELD_KEYS,
    empty_fields,
    fields_from_decode,
    fields_from_scrape,
    merge_field_dict,
)
from core.item_finalize import finalize_item
from core.pipeline import ProcessResult, ReportPipeline
from gui.dnd import collect_image_paths, hook_dropfiles
from gui.settings_dialog import SETTING_KEYS, SettingsDialog

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}

FIELD_LABELS = {
    "qr_content": "二维码内容",
    "order_no": "委托编号",
    "report_no": "报告编号",
    "project_name": "工程名称",
    "section": "标段",
    "sample_name": "样品名称",
    "report_date": "报告日期",
    "ocr_content": "OCR 内容",
}


class OrganizeTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, repo: Repository) -> None:
        super().__init__(parent)
        self.repo = repo

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._worker: BatchWorker | None = None
        self._paths: list[Path] = []
        self._current_index: int = -1
        self._pipeline: ReportPipeline | None = None
        self._decoded = None
        self._photo_ref = None
        self._busy = False
        self._last_result: ProcessResult | None = None

        self._pipeline_auto = False
        self._pipeline_stop = False
        self._pipeline_total = 0
        self._pipeline_done_count = 0
        self._pipeline_stats = {"success": 0, "failed": 0, "skipped": 0}

        self._ml_queue: queue.Queue = queue.Queue()
        self._ml_pump_running = False
        self._bulk_adding = False
        self._decode_future = None
        self._decode_ctx: tuple[Path, bool] | None = None
        self._async_ml_busy = False

        self.mode_var = tk.StringVar(value="sequential")
        self.worker_count_var = tk.IntVar(value=int(repo.get_setting("batch_workers") or "6"))

        self._build_ui()
        self._setup_dnd()
        self.after(200, self._drain_log)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="整理方式").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Radiobutton(
            toolbar,
            text="逐个整理",
            variable=self.mode_var,
            value="sequential",
            command=self._on_mode_change,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            toolbar,
            text="后台批量",
            variable=self.mode_var,
            value="batch",
            command=self._on_mode_change,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(toolbar, text="进程数").pack(side=tk.LEFT)
        self.worker_spin = ttk.Spinbox(
            toolbar,
            from_=5,
            to=10,
            width=4,
            textvariable=self.worker_count_var,
        )
        self.worker_spin.pack(side=tk.LEFT, padx=4)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        self.start_btn = ttk.Button(toolbar, text="开始流水线", command=self._start_batch)
        self.start_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="停止", command=self._stop_batch).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="设置…", command=self._open_settings).pack(side=tk.RIGHT, padx=2)

        outer_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        outer_paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        work_area = ttk.Frame(outer_paned)
        outer_paned.add(work_area, weight=5)

        main_paned = ttk.PanedWindow(work_area, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # —— 左侧：待处理 ——
        left = ttk.LabelFrame(main_paned, text="待处理（可拖入文件/文件夹）", padding=4)
        main_paned.add(left, weight=1)

        left_btns = ttk.Frame(left)
        left_btns.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(left_btns, text="添加文件", command=self._add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_btns, text="添加文件夹", command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_btns, text="移除", command=self._remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_btns, text="清空", command=self._clear_list).pack(side=tk.LEFT, padx=2)

        self.listbox = tk.Listbox(left, selectmode=tk.EXTENDED, exportselection=False)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self._listbox_select_event = "<<ListboxSelect>>"
        self.listbox.bind(self._listbox_select_event, self._on_list_select)

        # —— 中间：预览 ——
        center = ttk.LabelFrame(main_paned, text="报告预览", padding=4)
        main_paned.add(center, weight=2)

        pipe_row = ttk.Frame(center)
        pipe_row.pack(fill=tk.X, pady=(0, 4))
        self.pipeline_stage_var = tk.StringVar(value="")
        ttk.Label(pipe_row, textvariable=self.pipeline_stage_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.pipeline_progress = ttk.Progressbar(pipe_row, mode="determinate", length=200)
        self.pipeline_progress.pack(side=tk.RIGHT, padx=(8, 0))

        self.preview_label = tk.Label(
            center, text="选择左侧文件开始", anchor=tk.CENTER, bg="#f0f0f0"
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        seq_btns = ttk.Frame(center)
        seq_btns.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(seq_btns, text="识别并爬取", command=self._seq_scrape).pack(side=tk.LEFT, padx=2)
        ttk.Button(seq_btns, text="完成并下一份", command=self._seq_finish_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(seq_btns, text="手动落库", command=self._seq_manual_save).pack(side=tk.LEFT, padx=2)
        ttk.Button(seq_btns, text="放弃", command=self._seq_skip).pack(side=tk.LEFT, padx=2)

        # —— 右侧：字段 ——
        right = ttk.LabelFrame(main_paned, text="识别信息（可编辑；扫码枪可扫入二维码框后回车）", padding=6)
        main_paned.add(right, weight=1)

        self.field_vars: dict[str, tk.StringVar] = {}
        for key in UI_ENTRY_KEYS:
            row = ttk.Frame(right)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=FIELD_LABELS.get(key, key), width=14).pack(side=tk.LEFT)
            v = tk.StringVar()
            self.field_vars[key] = v
            ent = ttk.Entry(row, textvariable=v)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            if key == "qr_content":
                ent.bind("<Return>", lambda _e: self._on_qr_enter())

        ocr_frame = ttk.Frame(right)
        ocr_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        ttk.Label(ocr_frame, text=FIELD_LABELS[OCR_FIELD_KEY], width=14).pack(
            anchor=tk.NW, side=tk.LEFT
        )
        ocr_box = ttk.Frame(ocr_frame)
        ocr_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ocr_text = tk.Text(ocr_box, height=6, wrap=tk.WORD, state=tk.DISABLED)
        ocr_scroll = ttk.Scrollbar(ocr_box, command=self.ocr_text.yview)
        self.ocr_text.config(yscrollcommand=ocr_scroll.set)
        self.ocr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ocr_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.field_vars["anti_fake_code"] = tk.StringVar()

        log_frame = ttk.LabelFrame(outer_paned, text="日志（可拖动上边缘调整高度）", padding=4)
        outer_paned.add(log_frame, weight=1)

        self.log_text = tk.Text(log_frame, height=5, state=tk.DISABLED, wrap=tk.WORD)
        scroll_log = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scroll_log.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_log.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="就绪 — 可拖入图片或文件夹")
        ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, padx=6, pady=(0, 6)
        )
        self._on_mode_change()
        self.after(
            100,
            lambda: self._append_log("整理页 v4：识别在子进程执行，界面保持响应"),
        )

    def _suspend_list_select(self) -> None:
        self.listbox.unbind(self._listbox_select_event)

    def _resume_list_select(self) -> None:
        self.listbox.bind(self._listbox_select_event, self._on_list_select)

    def _schedule_ml_pump(self) -> None:
        """解码走子进程；爬取走后台线程，主线程只刷新 UI。"""
        if self._ml_pump_running:
            return
        self._ml_pump_running = True
        self.after(0, self._ml_pump_on_main)

    def _ml_pump_on_main(self) -> None:
        self._ml_pump_running = False
        if self._decode_future is not None:
            self._poll_decode_future()
            return
        if self._async_ml_busy:
            self.after(50, self._schedule_ml_pump)
            return
        try:
            job = self._ml_queue.get_nowait()
        except queue.Empty:
            return
        try:
            self._run_ml_job(job)
        except Exception as e:
            self._append_log(f"任务异常: {e}")
        if (
            self._decode_future is None
            and not self._async_ml_busy
            and not self._ml_queue.empty()
        ):
            self._schedule_ml_pump()

    def _begin_decode_subprocess(self, path: Path, pipeline: bool) -> None:
        self.status_var.set(f"识别中: {path.name}…")
        if pipeline:
            self._update_pipeline_ui(
                f"[{self._pipeline_done_count + 1}/{self._pipeline_total}] OCR/QR 识别…"
            )
        self.update_idletasks()
        self._decode_ctx = (path, pipeline)
        self._decode_future = submit_decode(self._settings_dict(), str(path.resolve()))
        self.after(50, self._poll_decode_future)

    def _poll_decode_future(self) -> None:
        if self._decode_future is None or self._decode_ctx is None:
            return
        if not self._decode_future.done():
            self.after(50, self._poll_decode_future)
            return
        path, pipeline = self._decode_ctx
        fut = self._decode_future
        self._decode_future = None
        self._decode_ctx = None
        try:
            outcome = dict_to_decode_outcome(fut.result())
            self._apply_decode(outcome, path, pipeline=pipeline)
        except Exception as e:
            self._handle_decode_error(path, str(e), pipeline)
        if not self._ml_queue.empty():
            self._schedule_ml_pump()

    def _run_ml_job(self, job) -> None:
        if job[0] == "scrape":
            _, path, pipeline, settings, fields, decoded = job
            self._run_scrape_in_thread(path, pipeline, settings, fields, decoded)
            return
        path, pipeline = job
        self._begin_decode_subprocess(path, pipeline)

    def _run_scrape_in_thread(
        self,
        path: Path,
        pipeline: bool,
        settings: dict,
        fields: dict,
        decoded,
    ) -> None:
        self._async_ml_busy = True

        def work() -> None:
            try:
                pl = self._get_pipeline()
                dec = decoded
                if dec is None:
                    from core.qr_input import build_decode_from_fields

                    dec = build_decode_from_fields(path.name, fields)
                result = pl.scrape_decoded(
                    dec,
                    limis_base=settings.get("limis_base"),
                    limis_user=settings.get("limis_user"),
                    limis_password=settings.get("limis_password"),
                    limis_auth_type=settings.get("limis_auth_type") or "1",
                    report_no=fields.get("report_no") or None,
                    anti_fake_code=fields.get("anti_fake_code") or None,
                )
                self.after(
                    0,
                    lambda r=result, pl=pipeline: self._finish_scrape_async(r, pl),
                )
            except Exception as e:
                self.after(
                    0,
                    lambda err=e, p=path, pl=pipeline: self._finish_scrape_async_error(
                        p, str(err), pl
                    ),
                )

        threading.Thread(target=work, daemon=True).start()

    def _finish_scrape_async(self, result: ProcessResult, pipeline: bool) -> None:
        self._async_ml_busy = False
        self._apply_scrape(result, pipeline=pipeline)
        if not self._ml_queue.empty():
            self._schedule_ml_pump()

    def _finish_scrape_async_error(self, path: Path, err: str, pipeline: bool) -> None:
        self._async_ml_busy = False
        self._on_scrape_worker_error(path, err, pipeline)
        if not self._ml_queue.empty():
            self._schedule_ml_pump()

    def _on_scrape_worker_error(self, path: Path, err: str, pipeline: bool) -> None:
        self._busy = False
        self._append_log(f"爬取异常 {path.name}: {err}")
        self.status_var.set(err)
        if pipeline:
            self._on_pipeline_scrape_failed(path, err)

    def _handle_decode_error(self, path: Path, err: str, pipeline: bool) -> None:
        self._busy = False
        self._append_log(f"解码异常 {path.name}: {err}")
        if pipeline:
            self._on_pipeline_decode_failed(path, err)
        else:
            self.status_var.set(err)

    def _setup_dnd(self) -> None:
        # 只注册一次，避免同一次拖放触发两次 _add_paths
        ok = hook_dropfiles(self.winfo_toplevel(), self._add_paths)
        if ok:
            self._append_log("拖放已启用（主线程队列模式）")
        else:
            self._append_log("提示：安装 windnd 后可拖放添加（pip install windnd）")

    def _on_mode_change(self) -> None:
        batch = self.mode_var.get() == "batch"
        state = "normal" if batch else "disabled"
        self.worker_spin.config(state=state)
        self.start_btn.config(text="开始批量" if batch else "开始流水线")

    def _update_pipeline_ui(self, stage: str, *, value: int | None = None) -> None:
        self.pipeline_stage_var.set(stage)
        if value is not None:
            self.pipeline_progress["value"] = value

    def _settings_dict(self) -> dict[str, str | None]:
        return self.repo.get_settings(SETTING_KEYS)

    def _append_log(self, msg: str) -> None:
        self._log_queue.put(msg)

    def _drain_log(self) -> None:
        while True:
            try:
                msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.after(200, self._drain_log)

    def _get_pipeline(self) -> ReportPipeline:
        if self._pipeline is None:
            settings = self._settings_dict()
            ocr_dir = settings.get("rapidocr_dir")
            weights = settings.get("scanreport_weights_dir")
            self._pipeline = ReportPipeline(
                weights_folder=Path(weights) if weights else None,
                ocr_dir=Path(ocr_dir) if ocr_dir else None,
                ocr_enabled=True,
            )
        return self._pipeline

    def _end_bulk_add(self, *, added: int | None = None) -> None:
        self.listbox.selection_clear(0, tk.END)
        self._bulk_adding = False
        self._resume_list_select()
        if added is not None and added > 0:
            self.status_var.set(
                f"已添加 {added} 个文件，共 {len(self._paths)} 个"
                " — 点击列表项预览，或「开始流水线」"
            )
        elif added == 0:
            self.status_var.set(f"共 {len(self._paths)} 个文件（无新图片）")

    def _add_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._bulk_adding = True
        self._suspend_list_select()
        self.status_var.set("正在扫描图片…")
        self.update_idletasks()
        self.after_idle(lambda p=list(paths): self._add_paths_impl(p))

    def _add_paths_impl(self, paths: list[Path]) -> None:
        try:
            paths = collect_image_paths(paths)
            seen = {p.resolve() for p in self._paths}
            to_add: list[Path] = []
            for p in paths:
                if p.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                key = p.resolve()
                if key not in seen:
                    seen.add(key)
                    to_add.append(p)
            if not to_add:
                self._end_bulk_add(added=0)
                return
            self._paths.extend(to_add)
            self._append_listbox_chunk(to_add, 0)
        except Exception as e:
            self._bulk_adding = False
            self._resume_list_select()
            self._append_log(f"添加文件失败: {e}")
            self.status_var.set("添加失败")

    def _append_listbox_chunk(self, items: list[Path], start: int, *, chunk: int = 80) -> None:
        end = min(start + chunk, len(items))
        for p in items[start:end]:
            self.listbox.insert(tk.END, str(p))
        if end < len(items):
            self.after(1, lambda: self._append_listbox_chunk(items, end, chunk=chunk))
            return
        self._end_bulk_add(added=len(items))

    def _add_files(self) -> None:
        files = filedialog.askopenfilenames(
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All", "*.*")]
        )
        if files:
            self._add_paths([Path(f) for f in files])

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self._add_paths([Path(folder)])

    def _remove_selected(self) -> None:
        sel = list(self.listbox.curselection())
        if not sel:
            return
        for i in reversed(sel):
            self.listbox.delete(i)
            del self._paths[i]
        if self._paths:
            idx = min(sel[0], len(self._paths) - 1)
            self._load_item(idx)
        else:
            self._current_index = -1
            self._clear_preview()

    def _clear_list(self) -> None:
        self.listbox.delete(0, tk.END)
        self._paths.clear()
        self._current_index = -1
        self._decoded = None
        self._clear_preview()
        for v in self.field_vars.values():
            v.set("")
        self._clear_ocr_text()

    def _clear_preview(self) -> None:
        self._photo_ref = None
        self.preview_label.config(image="", text="无预览")

    def _on_list_select(self, _evt=None) -> None:
        if self._bulk_adding or self._pipeline_auto or self.mode_var.get() != "sequential" or self._busy:
            return
        sel = self.listbox.curselection()
        if not sel:
            return
        self._load_item(sel[0])

    def _load_item(self, index: int, *, pipeline: bool = False) -> None:
        if index < 0 or index >= len(self._paths):
            return
        if self._busy and not pipeline:
            return
        self._current_index = index
        path = self._paths[index]
        total = self._pipeline_total if pipeline else len(self._paths)
        pos = self._pipeline_done_count + 1 if pipeline else index + 1
        self.status_var.set(f"加载 {pos}/{total}: {path.name}")
        if pipeline:
            self._update_pipeline_ui(f"[{pos}/{total}] 显示 · {path.name}", value=pos - 1)
        self._show_image(path)
        self._busy = True
        self._ml_queue.put((path, pipeline))
        self._schedule_ml_pump()

    def _show_image(self, path: Path) -> None:
        self._photo_ref = show_image_on_label(
            self.preview_label, path, max_size=(520, 680), empty_text="无预览"
        )

    def _apply_decode(self, outcome, path: Path, *, pipeline: bool = False) -> None:
        self._busy = False
        if outcome.status != "success" or not outcome.decoded:
            self._decoded = None
            for v in self.field_vars.values():
                v.set("")
            self._clear_ocr_text()
            self._append_log(f"解码失败 {path.name}: {outcome.error}")
            self.status_var.set(outcome.error or "解码失败")
            if pipeline:
                self._on_pipeline_decode_failed(path, outcome.error or "解码失败")
            return

        self._decoded = outcome.decoded
        self._last_result = None
        qr_text = outcome.qr_text if outcome.decode_method == "qr" else ""
        fields = fields_from_decode(
            qr_content=qr_text,
            report_type=outcome.report_type,
            report_no=outcome.report_no,
            anti_fake_code=outcome.anti_fake_code,
            ocr_preview=outcome.ocr_preview,
            decode_method=outcome.decode_method,
        )
        self._set_fields(fields)
        self.status_var.set(
            f"{path.name} — {outcome.report_type or '?'} / {outcome.decode_method or '?'}"
        )
        if pipeline and not self._pipeline_stop:
            self.after(80, self._seq_scrape)

    def _set_fields(self, fields: dict[str, str]) -> None:
        for k, v in fields.items():
            if k in self.field_vars:
                self.field_vars[k].set(v)
        ocr = fields.get(OCR_FIELD_KEY, "")
        self.ocr_text.config(state=tk.NORMAL)
        self.ocr_text.delete("1.0", tk.END)
        if ocr:
            self.ocr_text.insert("1.0", ocr)
        self.ocr_text.config(state=tk.DISABLED)

    def _clear_ocr_text(self) -> None:
        self.ocr_text.config(state=tk.NORMAL)
        self.ocr_text.delete("1.0", tk.END)
        self.ocr_text.config(state=tk.DISABLED)

    def _read_fields(self) -> dict[str, str]:
        out = {k: self.field_vars[k].get().strip() for k in FIELD_KEYS if k in self.field_vars}
        out[OCR_FIELD_KEY] = self.ocr_text.get("1.0", tk.END).strip()
        return out

    def _on_qr_enter(self) -> None:
        text = self.field_vars["qr_content"].get().strip()
        if not text:
            return
        from core.qr_input import parse_qr_text

        parsed = parse_qr_text(text)
        if parsed.get("report_no"):
            self.field_vars["report_no"].set(parsed["report_no"])
        if parsed.get("anti_fake_code"):
            self.field_vars["anti_fake_code"].set(parsed["anti_fake_code"])
        self._seq_scrape()

    def _current_path(self) -> Path | None:
        if 0 <= self._current_index < len(self._paths):
            return self._paths[self._current_index]
        return None

    def _seq_scrape(self) -> None:
        path = self._current_path()
        if not path:
            messagebox.showwarning("提示", "请先选择文件")
            return
        if self._decoded is None:
            fields = self._read_fields()
            if not fields.get("report_no"):
                if self._pipeline_auto:
                    self._on_pipeline_scrape_failed(path, "无报告编号")
                    return
                messagebox.showwarning("提示", "无解码结果，请填写报告编号或扫码")
                return
        settings = self._settings_dict()
        fields = self._read_fields()
        self._busy = True
        self.status_var.set("爬取中…")
        pipeline = self._pipeline_auto
        if pipeline:
            self._update_pipeline_ui(
                f"[{self._pipeline_done_count + 1}/{self._pipeline_total}] 爬取数据…"
            )

        self._ml_queue.put(
            (
                "scrape",
                path,
                pipeline,
                dict(settings),
                dict(fields),
                self._decoded,
            )
        )
        self._schedule_ml_pump()

    def _apply_scrape(self, result: ProcessResult, *, pipeline: bool = False) -> None:
        self._busy = False
        self._last_result = result
        scraped = (
            fields_from_scrape(result.scrape, result.report_type)
            if result.scrape
            else empty_fields()
        )
        has_ui_data = any(
            scraped.get(k)
            for k in UI_FIELD_KEYS
            if k not in ("qr_content", OCR_FIELD_KEY)
        )

        if result.status == "success" and result.scrape and has_ui_data:
            f = merge_field_dict(self._read_fields(), scraped)
            if scraped.get("report_no"):
                result = ProcessResult(
                    result.status,
                    result.source_image,
                    report_type=result.report_type,
                    report_no=scraped["report_no"],
                    decode_method=result.decode_method,
                    scrape=result.scrape,
                    decoded=result.decoded,
                )
                self._last_result = result
            self._set_fields(f)
            ch = {"limis": "内网", "institute": "院网", "association": "协会"}.get(
                result.report_type or "", result.report_type
            )
            self._append_log(f"爬取成功 [{ch}]: {result.report_no}")
            if pipeline:
                self._update_pipeline_ui(
                    f"[{self._pipeline_done_count + 1}/{self._pipeline_total}] 入库整理…"
                )
                self.after(80, self._seq_finish_next)
            else:
                self.status_var.set("爬取成功，请核对右侧字段后「完成并下一份」")
        else:
            if scraped.get("report_no"):
                self.field_vars["report_no"].set(scraped["report_no"])
            err = result.error or "爬取无有效数据（常见于报告编号 OCR 错误，请改编号后重试）"
            self._append_log(f"爬取失败: {err}")
            self.status_var.set(err)
            if pipeline:
                path = self._current_path()
                if path:
                    self._on_pipeline_scrape_failed(path, err)
            else:
                messagebox.showwarning(
                    "爬取未成功",
                    err + "\n\n请检查报告编号/防伪码，或扫码枪输入二维码后回车重试。",
                )

    def _seq_finish_next(self) -> None:
        path = self._current_path()
        if not path:
            return
        settings = self._settings_dict()
        if not settings.get("output_root"):
            messagebox.showwarning("提示", "请先在设置中指定输出根目录")
            return
        fields = self._read_fields()
        result = self._last_result
        force_partial = True
        if result and result.status == "success" and result.scrape:
            force_partial = False
        else:
            if not fields.get("report_no"):
                messagebox.showwarning("提示", "需要报告编号")
                return
            result = ProcessResult(
                "failed",
                path.name,
                report_type=self._decoded.report_type if self._decoded else "unknown",
                report_no=fields.get("report_no"),
                decode_method=self._decoded.decode_source if self._decoded else "manual",
                error="未完成爬取",
            )

        ok, msg, dest, _fi = finalize_item(
            self.repo,
            Path(settings["output_root"]),
            path,
            result,
            manual_fields=fields,
            force_partial=force_partial,
        )
        if ok:
            self._append_log(f"已整理 {path.name} -> {msg}")
            if self._pipeline_auto:
                self._pipeline_stats["success"] += 1
            self._remove_current_and_advance()
        else:
            if self._pipeline_auto:
                self._pipeline_stats["failed"] += 1
                self._append_log(f"入库失败 {path.name}: {msg}")
                self._pipeline_advance_after_fail()
            else:
                messagebox.showerror("失败", msg)

    def _seq_manual_save(self) -> None:
        path = self._current_path()
        if not path:
            return
        settings = self._settings_dict()
        if not settings.get("output_root"):
            messagebox.showwarning("提示", "请先在设置中指定输出根目录")
            return
        fields = self._read_fields()
        if not fields.get("report_no"):
            messagebox.showwarning("提示", "请填写报告编号")
            return
        ch = self._decoded.report_type if self._decoded else "unknown"
        result = ProcessResult(
            "failed",
            path.name,
            report_type=ch,
            report_no=fields["report_no"],
            decode_method=self._decoded.decode_source if self._decoded else "manual",
            error="manual entry",
        )
        ok, msg, _, _ = finalize_item(
            self.repo,
            Path(settings["output_root"]),
            path,
            result,
            manual_fields=fields,
            force_partial=True,
        )
        if ok:
            self._append_log(f"手动落库 {path.name} -> {msg}")
            self._remove_current_and_advance()
        else:
            messagebox.showerror("失败", msg)

    def _seq_skip(self) -> None:
        if messagebox.askyesno("放弃", "跳过当前文件，不写入数据库？"):
            self._remove_current_and_advance()

    def _remove_current_and_advance(self) -> None:
        idx = self._current_index
        if idx < 0:
            return
        self.listbox.delete(idx)
        del self._paths[idx]
        self._decoded = None
        self._last_result = None
        for v in self.field_vars.values():
            v.set("")
        self._clear_ocr_text()
        if self._pipeline_auto:
            self._pipeline_done_count += 1
            if self._paths and not self._pipeline_stop:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(0)
                self.after(400, lambda: self._load_item(0, pipeline=True))
            else:
                self._finish_sequential_pipeline()
            return
        if self._paths:
            next_idx = min(idx, len(self._paths) - 1)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(next_idx)
            self._load_item(next_idx)
        else:
            self._current_index = -1
            self._clear_preview()
            self.status_var.set("全部处理完毕")

    def _open_settings(self) -> None:
        SettingsDialog(
            self.winfo_toplevel(),
            self.repo,
            on_saved=lambda: self._append_log("设置已保存"),
        )

    def _start_sequential_pipeline(self) -> None:
        if not self._paths:
            messagebox.showwarning("提示", "请先添加报告图片")
            return
        settings = self._settings_dict()
        if not settings.get("output_root"):
            messagebox.showwarning("提示", "请先在设置中指定输出根目录")
            return
        self._pipeline_auto = True
        self._pipeline_stop = False
        self._pipeline_total = len(self._paths)
        self._pipeline_done_count = 0
        self._pipeline_stats = {"success": 0, "failed": 0, "skipped": 0}
        self.pipeline_progress["maximum"] = self._pipeline_total
        self.pipeline_progress["value"] = 0
        self._append_log(f"流水线开始，共 {self._pipeline_total} 张")
        self.status_var.set("流水线运行中…")
        self.listbox.selection_clear(0, tk.END)
        if self._paths:
            self.listbox.selection_set(0)
            self._load_item(0, pipeline=True)

    def _finish_sequential_pipeline(self) -> None:
        self._pipeline_auto = False
        s = self._pipeline_stats
        msg = f"流水线结束：成功 {s['success']}，失败 {s['failed']}，跳过 {s['skipped']}"
        self._append_log(msg)
        self.status_var.set(msg)
        self._update_pipeline_ui("流水线已结束", value=self._pipeline_total)
        self._current_index = -1
        self._clear_preview()

    def _pipeline_advance_after_fail(self) -> None:
        """流水线：跳过当前项继续下一张。"""
        idx = self._current_index
        if idx < 0:
            self._finish_sequential_pipeline()
            return
        self.listbox.delete(idx)
        if idx < len(self._paths):
            del self._paths[idx]
        self._decoded = None
        self._last_result = None
        self._pipeline_done_count += 1
        if self._paths and not self._pipeline_stop:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self.after(400, lambda: self._load_item(0, pipeline=True))
        else:
            self._finish_sequential_pipeline()

    def _on_pipeline_decode_failed(self, path: Path, err: str) -> None:
        self._busy = False
        if not self._pipeline_auto:
            return
        self._pipeline_stats["skipped"] += 1
        self._append_log(f"流水线跳过(解码) {path.name}: {err}")
        self._pipeline_advance_after_fail()

    def _on_pipeline_scrape_failed(self, path: Path, err: str) -> None:
        if not self._pipeline_auto:
            return
        self._pipeline_stats["failed"] += 1
        self._append_log(f"流水线跳过(爬取) {path.name}: {err}")
        self._pipeline_advance_after_fail()

    def _start_batch(self) -> None:
        if self.mode_var.get() != "batch":
            self._start_sequential_pipeline()
            return
        if not self._paths:
            messagebox.showwarning("提示", "请先添加报告图片")
            return
        settings = self._settings_dict()
        if not settings.get("output_root"):
            messagebox.showwarning("提示", "请先在设置中指定输出根目录")
            return

        try:
            n = int(self.worker_count_var.get())
        except (ValueError, tk.TclError):
            n = 6
        n = max(5, min(10, n))
        self.repo.set_setting("batch_workers", str(n))

        self._append_log(f"开始批量 {len(self._paths)} 个文件，{n} 进程…")
        self.status_var.set("批量处理中…")

        def on_progress(cur: int, total: int, name: str) -> None:
            self.after(0, lambda: self.status_var.set(f"{cur}/{total} {name}"))

        def on_done(counts: dict[str, int], err: str | None) -> None:
            def _finish() -> None:
                if err:
                    messagebox.showerror("批处理", err)
                msg = (
                    f"完成：成功 {counts['success']}，失败 {counts['failed']}，"
                    f"跳过 {counts['skipped']}"
                )
                self._append_log(msg)
                self.status_var.set(msg)
                if counts["success"] and settings.get("output_root"):
                    if messagebox.askyesno("完成", msg + "\n\n打开输出目录？"):
                        self._open_folder(settings["output_root"])

            self.after(0, _finish)

        self._worker = BatchWorker(
            self.repo,
            settings,
            on_log=lambda m: self.after(0, lambda: self._append_log(m)),
            on_progress=lambda c, t, n: self.after(0, lambda: on_progress(c, t, n)),
            on_done=lambda c, e: self.after(0, lambda: on_done(c, e)),
            worker_count=n,
        )
        self._worker.start(list(self._paths))

    def _stop_batch(self) -> None:
        if self._pipeline_auto:
            self._pipeline_stop = True
            self._pipeline_auto = False
            self._append_log("流水线已停止")
            self.status_var.set("流水线已停止")
            self._update_pipeline_ui("已停止")
            return
        if self._worker:
            self._worker.stop()

    @staticmethod
    def _open_folder(path: str) -> None:
        p = Path(path)
        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=False)
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
