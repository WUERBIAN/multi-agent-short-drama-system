"""简化版 Tkinter 图形界面。

功能只保留四项：
1. 生成短剧剧本
2. 查看生成日志
3. 查看剧本结果并导出/下载
4. 删除生成出的剧本/日志信息

说明：界面保持极简，但后台保留多智能体协作流程，
生成时会进行“制片人1次、编剧策划1次、编剧团队按集生成、导演审核1次、定稿1次”的多轮 DeepSeek API 调用，并在界面实时显示调用进度。
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from app.config import settings
from app.services.deepseek_client import DeepSeekClient
from app.services.script_generator import ScriptGenerator, ScriptRequest
from app.services import file_manager


class ShortDramaSimpleGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("短剧剧本生成系统 - DeepSeek 多智能体版")
        self.geometry("1180x760")
        self.minsize(980, 650)

        self.message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.current_script_path: Optional[Path] = None
        self.current_log_path: Optional[Path] = None
        self.script_paths: list[Path] = []
        self.log_paths: list[Path] = []

        self._build_ui()
        self.refresh_all_lists()
        self.after(100, self._drain_queue)

    # ----------------------------- UI -----------------------------
    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.generate_tab = ttk.Frame(self.notebook, padding=10)
        self.logs_tab = ttk.Frame(self.notebook, padding=10)
        self.results_tab = ttk.Frame(self.notebook, padding=10)
        self.delete_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.generate_tab, text="1. 生成短剧剧本")
        self.notebook.add(self.logs_tab, text="2. 查看生成日志")
        self.notebook.add(self.results_tab, text="3. 查看/下载剧本结果")
        self.notebook.add(self.delete_tab, text="4. 删除剧本/日志信息")

        self._build_generate_tab()
        self._build_logs_tab()
        self._build_results_tab()
        self._build_delete_tab()

        bottom = ttk.Frame(root)
        bottom.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="就绪。未填写 DeepSeek API Key 时无法生成。后台采用多智能体多轮 API 调用。")
        ttk.Label(bottom, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="刷新全部列表", command=self.refresh_all_lists).grid(row=0, column=1, sticky="e")

    def _build_generate_tab(self) -> None:
        self.generate_tab.columnconfigure(1, weight=1)
        self.generate_tab.rowconfigure(2, weight=1)

        form = ttk.LabelFrame(self.generate_tab, text="生成参数（后台采用多智能体多轮 API 调用）", padding=10)
        form.grid(row=0, column=0, columnspan=2, sticky="ew")
        for i in range(4):
            form.columnconfigure(i, weight=1 if i in (1, 3) else 0)

        self.api_key_var = tk.StringVar(value=os.getenv("DEEPSEEK_API_KEY", settings.DEEPSEEK_API_KEY))
        self.model_var = tk.StringVar(value=os.getenv("DEEPSEEK_MODEL", settings.DEEPSEEK_MODEL))
        self.title_var = tk.StringVar(value="我的短剧项目")
        self.theme_var = tk.StringVar(value="焦虑与自洽")
        self.genre_var = tk.StringVar(value="都市情感")
        self.platform_var = tk.StringVar(value="抖音")
        self.episode_var = tk.IntVar(value=3)
        self.duration_var = tk.IntVar(value=90)
        self.audience_var = tk.StringVar(value="18-35岁年轻人")
        self.commercial_var = tk.StringVar(value="广告植入")
        self.min_words_var = tk.IntVar(value=1200)
        self.scene_count_var = tk.IntVar(value=4)
        self.detail_level_var = tk.StringVar(value="标准")
        self.progress_value = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="进度：等待开始")

        row = 0
        self._add_entry(form, row, "DeepSeek API Key（必填）", self.api_key_var, show="*")
        self._add_entry(form, row, "模型", self.model_var, col=2)
        row += 1
        self._add_entry(form, row, "项目名称", self.title_var)
        self._add_entry(form, row, "主题/创意", self.theme_var, col=2)
        row += 1
        self._add_combo(form, row, "剧本类型", self.genre_var, ["都市情感", "悬疑推理", "喜剧搞笑", "青春校园", "古装穿越", "现实主义", "家庭伦理"])
        self._add_combo(form, row, "目标平台", self.platform_var, ["抖音", "快手", "微信视频号", "小红书", "B站"] , col=2)
        row += 1
        self._add_spin(form, row, "集数", self.episode_var, 1, 30)
        self._add_spin(form, row, "每集时长/秒", self.duration_var, 30, 300, col=2)
        row += 1
        self._add_entry(form, row, "目标受众", self.audience_var)
        self._add_entry(form, row, "商业需求", self.commercial_var, col=2)
        row += 1
        self._add_spin(form, row, "每集最低字数", self.min_words_var, 500, 5000)
        self._add_spin(form, row, "每集场景数", self.scene_count_var, 2, 8, col=2)
        row += 1
        self._add_combo(form, row, "生成详细程度", self.detail_level_var, ["简略", "标准", "详细", "非常详细"])
        row += 1

        extra_box = ttk.LabelFrame(self.generate_tab, text="补充要求（可选）", padding=10)
        extra_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 8))
        extra_box.columnconfigure(0, weight=1)
        self.extra_text = tk.Text(extra_box, height=4, wrap=tk.WORD, font=("Microsoft YaHei UI", 10))
        self.extra_text.grid(row=0, column=0, sticky="ew")
        self.extra_text.insert("1.0", "例如：主角是刚毕业的女生；结尾要反转；场景尽量控制在办公室和出租屋。")

        run_box = ttk.Frame(self.generate_tab)
        run_box.grid(row=2, column=0, sticky="nsw", padx=(0, 10))
        self.generate_button = ttk.Button(run_box, text="开始生成短剧剧本", command=self.start_generate)
        self.generate_button.pack(fill=tk.X, pady=(0, 8))

        progress_frame = ttk.LabelFrame(run_box, text="多智能体调用进度", padding=8)
        progress_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Progressbar(progress_frame, variable=self.progress_value, maximum=100, mode="determinate").pack(fill=tk.X)
        ttk.Label(progress_frame, textvariable=self.progress_text_var, wraplength=210, justify=tk.LEFT).pack(fill=tk.X, pady=(6, 0))

        ttk.Button(run_box, text="打开剧本目录", command=lambda: file_manager.open_directory(settings.SCRIPTS_DIR)).pack(fill=tk.X, pady=4)
        ttk.Button(run_box, text="打开日志目录", command=lambda: file_manager.open_directory(settings.LOGS_DIR)).pack(fill=tk.X, pady=4)
        ttk.Button(run_box, text="清空生成输出窗口", command=lambda: self.generate_output.delete("1.0", tk.END)).pack(fill=tk.X, pady=4)

        output_box = ttk.LabelFrame(self.generate_tab, text="生成输出 / 多轮 API 调用日志", padding=8)
        output_box.grid(row=2, column=1, sticky="nsew")
        output_box.rowconfigure(0, weight=1)
        output_box.columnconfigure(0, weight=1)
        self.generate_output = tk.Text(output_box, wrap=tk.WORD, font=("Microsoft YaHei UI", 10))
        scroll = ttk.Scrollbar(output_box, command=self.generate_output.yview)
        self.generate_output.configure(yscrollcommand=scroll.set)
        self.generate_output.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _build_logs_tab(self) -> None:
        self.logs_tab.columnconfigure(1, weight=1)
        self.logs_tab.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(self.logs_tab, text="生成日志列表", padding=8)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self.log_listbox = tk.Listbox(left, width=42, exportselection=False)
        self.log_listbox.pack(fill=tk.BOTH, expand=True)
        self.log_listbox.bind("<<ListboxSelect>>", lambda _e: self.preview_selected_log())
        ttk.Button(left, text="刷新日志", command=self.refresh_logs).pack(fill=tk.X, pady=(8, 0))
        ttk.Button(left, text="打开日志目录", command=lambda: file_manager.open_directory(settings.LOGS_DIR)).pack(fill=tk.X, pady=4)

        right = ttk.LabelFrame(self.logs_tab, text="日志内容", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.log_preview = tk.Text(right, wrap=tk.WORD, font=("Microsoft YaHei UI", 10))
        scroll = ttk.Scrollbar(right, command=self.log_preview.yview)
        self.log_preview.configure(yscrollcommand=scroll.set)
        self.log_preview.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _build_results_tab(self) -> None:
        self.results_tab.columnconfigure(1, weight=1)
        self.results_tab.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(self.results_tab, text="剧本结果列表", padding=8)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self.script_listbox = tk.Listbox(left, width=44, exportselection=False)
        self.script_listbox.pack(fill=tk.BOTH, expand=True)
        self.script_listbox.bind("<<ListboxSelect>>", lambda _e: self.preview_selected_script())
        ttk.Button(left, text="刷新剧本", command=self.refresh_scripts).pack(fill=tk.X, pady=(8, 0))
        ttk.Button(left, text="查看选中剧本", command=self.preview_selected_script).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="导出/下载选中剧本", command=self.export_selected_script).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="打开剧本目录", command=lambda: file_manager.open_directory(settings.SCRIPTS_DIR)).pack(fill=tk.X, pady=4)

        right = ttk.LabelFrame(self.results_tab, text="剧本预览", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.script_preview = tk.Text(right, wrap=tk.WORD, font=("Microsoft YaHei UI", 10))
        scroll = ttk.Scrollbar(right, command=self.script_preview.yview)
        self.script_preview.configure(yscrollcommand=scroll.set)
        self.script_preview.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _build_delete_tab(self) -> None:
        self.delete_tab.columnconfigure(0, weight=1)
        self.delete_tab.columnconfigure(1, weight=1)
        self.delete_tab.rowconfigure(0, weight=1)

        script_box = ttk.LabelFrame(self.delete_tab, text="删除剧本文件", padding=8)
        script_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        script_box.rowconfigure(0, weight=1)
        script_box.columnconfigure(0, weight=1)
        self.delete_script_listbox = tk.Listbox(script_box, exportselection=False)
        self.delete_script_listbox.grid(row=0, column=0, sticky="nsew")
        ttk.Button(script_box, text="刷新剧本列表", command=self.refresh_scripts).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(script_box, text="删除选中剧本", command=self.delete_selected_script).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(script_box, text="清空全部剧本", command=self.clear_all_scripts).grid(row=3, column=0, sticky="ew", pady=4)

        log_box = ttk.LabelFrame(self.delete_tab, text="删除日志文件", padding=8)
        log_box.grid(row=0, column=1, sticky="nsew")
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)
        self.delete_log_listbox = tk.Listbox(log_box, exportselection=False)
        self.delete_log_listbox.grid(row=0, column=0, sticky="nsew")
        ttk.Button(log_box, text="刷新日志列表", command=self.refresh_logs).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(log_box, text="删除选中日志", command=self.delete_selected_log).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(log_box, text="清空全部日志", command=self.clear_all_logs).grid(row=3, column=0, sticky="ew", pady=4)

    def _add_entry(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, col: int = 0, show: str = "") -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=var, show=show).grid(row=row, column=col + 1, sticky="ew", pady=3)

    def _add_combo(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, values: list[str], col: int = 0) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3)
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly").grid(row=row, column=col + 1, sticky="ew", pady=3)

    def _add_spin(self, parent: ttk.Frame, row: int, label: str, var: tk.IntVar, min_v: int, max_v: int, col: int = 0) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3)
        ttk.Spinbox(parent, textvariable=var, from_=min_v, to=max_v).grid(row=row, column=col + 1, sticky="ew", pady=3)

    # --------------------------- generate --------------------------
    def _collect_request(self) -> ScriptRequest:
        return ScriptRequest(
            title=self.title_var.get().strip() or "未命名短剧",
            theme=self.theme_var.get().strip() or "待定主题",
            genre=self.genre_var.get().strip() or "都市情感",
            platform=self.platform_var.get().strip() or "抖音",
            episode_count=max(1, int(self.episode_var.get())),
            duration_per_episode=max(30, int(self.duration_var.get())),
            target_audience=self.audience_var.get().strip() or "18-35岁年轻人",
            commercial_requirements=self.commercial_var.get().strip(),
            extra_requirements=self.extra_text.get("1.0", tk.END).strip(),
            min_words_per_episode=max(500, int(self.min_words_var.get())),
            scene_count_per_episode=max(2, int(self.scene_count_var.get())),
            detail_level=self.detail_level_var.get().strip() or "标准",
        )

    def start_generate(self) -> None:
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        if not api_key:
            messagebox.showerror("缺少 API Key", "请先填写 DeepSeek API Key。没有 API Key 无法生成。")
            return
        if not model:
            messagebox.showerror("缺少模型", "请填写模型名称。")
            return

        os.environ["DEEPSEEK_API_KEY"] = api_key
        os.environ["DEEPSEEK_MODEL"] = model
        request = self._collect_request()

        self.generate_button.configure(state=tk.DISABLED)
        self.notebook.select(self.generate_tab)
        self.generate_output.insert(tk.END, "\n" + "=" * 70 + "\n")
        self.generate_output.insert(tk.END, f"开始生成：《{request.title}》\n")
        total_calls = 4 + request.episode_count
        self.generate_output.insert(tk.END, f"本次将进行 {total_calls} 次 DeepSeek API 调用：制片人1次 → 编剧策划1次 → 编剧团队按集生成{request.episode_count}次 → 导演审核1次 → 定稿1次。\n")
        self.generate_output.insert(tk.END, f"严格格式：每集不少于 {request.min_words_per_episode} 字，每集至少 {request.scene_count_per_episode} 个场景。\n")
        self.generate_output.see(tk.END)
        self.progress_value.set(0)
        self.progress_text_var.set("进度：0%｜等待启动多智能体流程")
        self.status_var.set("多智能体生成中，界面会实时显示每一次 API 调用进度……")

        thread = threading.Thread(target=self._generate_worker, args=(request, api_key, model), daemon=True)
        thread.start()

    def _generate_worker(self, request: ScriptRequest, api_key: str, model: str) -> None:
        def progress(percent: int, text: str) -> None:
            self.message_queue.put(("progress", {"percent": percent, "text": text}))

        try:
            client = DeepSeekClient(api_key=api_key, model=model)
            generator = ScriptGenerator(client)
            script_path, log_path, script_text = generator.generate(request, progress=progress)
            self.message_queue.put(("done", f"生成完成\n剧本：{script_path}\n日志：{log_path}\n"))
            self.message_queue.put(("script_preview", script_text))
        except Exception as exc:
            self.message_queue.put(("error", str(exc)))

    def _drain_queue(self) -> None:
        try:
            while True:
                msg_type, text = self.message_queue.get_nowait()
                if msg_type == "progress":
                    if isinstance(text, dict):
                        percent = int(text.get("percent", 0))
                        message = str(text.get("text", ""))
                        self.progress_value.set(percent)
                        self.progress_text_var.set(f"进度：{percent}%｜{message}")
                        self.status_var.set(message)
                        self._append_generate_output(f"【{percent:>3}%】{message}\n")
                    else:
                        self._append_generate_output(str(text) + "\n")
                elif msg_type == "done":
                    self.progress_value.set(100)
                    self.progress_text_var.set("进度：100%｜生成完成")
                    self._append_generate_output("\n✓ " + str(text) + "\n")
                    self.status_var.set("生成完成。")
                    self.generate_button.configure(state=tk.NORMAL)
                    self.refresh_all_lists()
                    self.notebook.select(self.results_tab)
                elif msg_type == "script_preview":
                    self.script_preview.delete("1.0", tk.END)
                    self.script_preview.insert(tk.END, text)
                elif msg_type == "error":
                    self.progress_value.set(0)
                    self.progress_text_var.set("进度：生成失败")
                    error_text = str(text)
                    self._append_generate_output("\n✗ 生成失败：" + error_text + "\n")
                    self.status_var.set("生成失败，详情请查看日志。")
                    self.generate_button.configure(state=tk.NORMAL)
                    self.refresh_all_lists()
                    messagebox.showerror("生成失败", error_text)
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def _append_generate_output(self, text: str) -> None:
        self.generate_output.insert(tk.END, text)
        self.generate_output.see(tk.END)

    # ----------------------------- lists ----------------------------
    def refresh_all_lists(self) -> None:
        self.refresh_scripts()
        self.refresh_logs()

    def refresh_scripts(self) -> None:
        self.script_paths = file_manager.list_scripts()
        for lb in (self.script_listbox, self.delete_script_listbox):
            lb.delete(0, tk.END)
            for path in self.script_paths:
                lb.insert(tk.END, path.name)

    def refresh_logs(self) -> None:
        self.log_paths = file_manager.list_logs()
        for lb in (self.log_listbox, self.delete_log_listbox):
            lb.delete(0, tk.END)
            for path in self.log_paths:
                lb.insert(tk.END, path.name)

    def _selected_script_path(self, listbox: tk.Listbox) -> Optional[Path]:
        selection = listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if index >= len(self.script_paths):
            return None
        return self.script_paths[index]

    def _selected_log_path(self, listbox: tk.Listbox) -> Optional[Path]:
        selection = listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if index >= len(self.log_paths):
            return None
        return self.log_paths[index]

    # ----------------------------- logs -----------------------------
    def preview_selected_log(self) -> None:
        path = self._selected_log_path(self.log_listbox)
        if not path:
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        self.log_preview.delete("1.0", tk.END)
        self.log_preview.insert(tk.END, content)
        self.status_var.set(f"正在查看日志：{path.name}")

    # ---------------------------- scripts ---------------------------
    def preview_selected_script(self) -> None:
        path = self._selected_script_path(self.script_listbox)
        if not path:
            messagebox.showinfo("提示", "请先选择一个剧本文件。")
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        self.script_preview.delete("1.0", tk.END)
        self.script_preview.insert(tk.END, content)
        self.status_var.set(f"正在查看剧本：{path.name}")

    def export_selected_script(self) -> None:
        path = self._selected_script_path(self.script_listbox)
        if not path:
            messagebox.showinfo("提示", "请先选择一个剧本文件。")
            return
        target_dir = filedialog.askdirectory(title="选择下载/导出位置")
        if not target_dir:
            return
        target = file_manager.export_file(path, Path(target_dir))
        messagebox.showinfo("导出成功", f"剧本已导出到：\n{target}")
        self.status_var.set(f"已导出剧本：{target}")

    # ----------------------------- delete ---------------------------
    def delete_selected_script(self) -> None:
        path = self._selected_script_path(self.delete_script_listbox)
        if not path:
            messagebox.showinfo("提示", "请先选择要删除的剧本。")
            return
        if messagebox.askyesno("确认删除", f"确定删除剧本文件吗？\n{path.name}"):
            file_manager.delete_file(path)
            self.refresh_scripts()
            self.status_var.set(f"已删除剧本：{path.name}")

    def delete_selected_log(self) -> None:
        path = self._selected_log_path(self.delete_log_listbox)
        if not path:
            messagebox.showinfo("提示", "请先选择要删除的日志。")
            return
        if messagebox.askyesno("确认删除", f"确定删除日志文件吗？\n{path.name}"):
            file_manager.delete_file(path)
            self.refresh_logs()
            self.status_var.set(f"已删除日志：{path.name}")

    def clear_all_scripts(self) -> None:
        if messagebox.askyesno("确认清空", "确定清空全部剧本文件吗？此操作不可恢复。"):
            count = file_manager.clear_directory(settings.SCRIPTS_DIR, settings.SCRIPT_SUFFIXES)
            self.refresh_scripts()
            self.script_preview.delete("1.0", tk.END)
            self.status_var.set(f"已清空 {count} 个剧本文件。")

    def clear_all_logs(self) -> None:
        if messagebox.askyesno("确认清空", "确定清空全部日志文件吗？此操作不可恢复。"):
            count = file_manager.clear_directory(settings.LOGS_DIR, settings.LOG_SUFFIXES)
            self.refresh_logs()
            self.log_preview.delete("1.0", tk.END)
            self.status_var.set(f"已清空 {count} 个日志文件。")


if __name__ == "__main__":
    app = ShortDramaSimpleGUI()
    app.mainloop()
