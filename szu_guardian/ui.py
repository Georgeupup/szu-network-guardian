from __future__ import annotations

import datetime as dt
import queue
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

from .local_log import LocalLog
from .models import AppConfig, ZONE_AUTO, ZONE_DORMITORY, ZONE_OFFICE
from .monitor import MonitorController, MonitorEvent
from .startup import is_autostart_enabled, set_autostart
from .storage import ConfigStore
from .tray import TrayController


COLORS = {
    "background": "#F3F6FB",
    "card": "#FFFFFF",
    "text": "#172033",
    "muted": "#6B778C",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "border": "#DCE3EE",
    "success": "#16A34A",
    "warning": "#D97706",
    "error": "#DC2626",
    "idle": "#94A3B8",
}

ZONE_LABELS = {
    "教学 / 办公区（实验室）": ZONE_OFFICE,
    "宿舍区": ZONE_DORMITORY,
    "自动尝试（实验性）": ZONE_AUTO,
}
ZONE_NAMES = {value: key for key, value in ZONE_LABELS.items()}
UI_LOG_RETENTION = dt.timedelta(hours=3)


class GuardianApp:
    def __init__(self, store: ConfigStore, launched_by_autostart: bool = False):
        self.store = store
        self.launched_by_autostart = launched_by_autostart
        self.config = store.load()
        self.events: queue.Queue[MonitorEvent] = queue.Queue()
        self.tray_actions: queue.Queue[str] = queue.Queue()
        self.monitor = MonitorController(self.events.put)
        self.local_log = LocalLog()
        self.log_entries: deque[tuple[dt.datetime, str]] = deque()
        self.is_exiting = False
        self.tray_notice_shown = False

        self.root = tk.Tk()
        self.root.title("SZU 网络守护")
        self.root.geometry("680x800")
        self.root.minsize(620, 720)
        self.root.configure(bg=COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_unmap)

        self.username_var = tk.StringVar(value=self.config.username)
        self.password_var = tk.StringVar(value=self.config.password)
        self.zone_var = tk.StringVar(
            value=ZONE_NAMES.get(self.config.zone, "教学 / 办公区（实验室）")
        )
        self.interval_var = tk.StringVar(value=str(self.config.interval_minutes))
        self.autostart_var = tk.BooleanVar(
            value=is_autostart_enabled() or self.config.autostart
        )
        self.start_on_launch_var = tk.BooleanVar(value=self.config.start_on_launch)
        self.password_visible = False

        self._configure_styles()
        self._build_ui()
        self.tray = TrayController(self.tray_actions.put)
        self.tray.start()
        self._append_log("程序已启动")
        self.root.after(120, self._process_events)
        self.root.after(250, self._handle_initial_start)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            "TFrame",
            background=COLORS["background"],
        )
        style.configure(
            "Card.TFrame",
            background=COLORS["card"],
        )
        style.configure(
            "TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "Card.TLabel",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "Muted.Card.TLabel",
            background=COLORS["card"],
            foreground=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Title.TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=COLORS["background"],
            foreground=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Section.Card.TLabel",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        style.configure(
            "TEntry",
            fieldbackground="#F8FAFC",
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=(10, 8),
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "TCombobox",
            fieldbackground="#F8FAFC",
            background="#F8FAFC",
            bordercolor=COLORS["border"],
            arrowsize=15,
            padding=(8, 7),
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "TSpinbox",
            fieldbackground="#F8FAFC",
            bordercolor=COLORS["border"],
            padding=(8, 7),
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "TCheckbutton",
            background=COLORS["card"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 9),
        )
        style.map(
            "TCheckbutton",
            background=[("active", COLORS["card"])],
        )
        style.configure(
            "Primary.TButton",
            background=COLORS["primary"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(18, 10),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", COLORS["primary_hover"]),
                ("disabled", "#A8B8D8"),
            ],
        )
        style.configure(
            "Secondary.TButton",
            background="#E9EFF9",
            foreground=COLORS["primary"],
            borderwidth=0,
            padding=(16, 10),
            font=("Microsoft YaHei UI", 10),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#DCE7F8")],
        )
        style.configure(
            "Ghost.TButton",
            background=COLORS["card"],
            foreground=COLORS["muted"],
            borderwidth=0,
            padding=(8, 7),
            font=("Microsoft YaHei UI", 9),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#F1F5F9")],
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(28, 22, 28, 18))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="SZU 网络守护", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="轻量、安静地守护你的校园网连接",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 16))

        status_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 14))
        status_card.pack(fill="x", pady=(0, 12))
        status_line = ttk.Frame(status_card, style="Card.TFrame")
        status_line.pack(fill="x")
        self.status_dot = tk.Canvas(
            status_line,
            width=18,
            height=18,
            bg=COLORS["card"],
            highlightthickness=0,
        )
        self.status_dot.pack(side="left")
        self.status_circle = self.status_dot.create_oval(
            4, 4, 14, 14, fill=COLORS["idle"], outline=""
        )
        self.status_label = ttk.Label(
            status_line,
            text="等待开始",
            style="Section.Card.TLabel",
        )
        self.status_label.pack(side="left", padx=(5, 0))
        self.detail_label = ttk.Label(
            status_line,
            text="尚未启动监控",
            style="Muted.Card.TLabel",
        )
        self.detail_label.pack(side="right")

        form_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 16))
        form_card.pack(fill="x", pady=(0, 12))
        ttk.Label(
            form_card,
            text="连接设置",
            style="Section.Card.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        form_card.columnconfigure(1, weight=1)

        self._form_label(form_card, "账号", 1)
        self.username_entry = ttk.Entry(
            form_card,
            textvariable=self.username_var,
        )
        self.username_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)

        self._form_label(form_card, "密码", 2)
        self.password_entry = ttk.Entry(
            form_card,
            textvariable=self.password_var,
            show="●",
        )
        self.password_entry.grid(row=2, column=1, sticky="ew", pady=5)
        self.show_password_button = ttk.Button(
            form_card,
            text="显示",
            style="Ghost.TButton",
            command=self._toggle_password,
            width=6,
        )
        self.show_password_button.grid(row=2, column=2, padx=(6, 0), pady=5)

        self._form_label(form_card, "区域", 3)
        self.zone_combo = ttk.Combobox(
            form_card,
            textvariable=self.zone_var,
            values=list(ZONE_LABELS),
            state="readonly",
        )
        self.zone_combo.grid(row=3, column=1, columnspan=2, sticky="ew", pady=5)

        self._form_label(form_card, "检测间隔", 4)
        interval_row = ttk.Frame(form_card, style="Card.TFrame")
        interval_row.grid(row=4, column=1, columnspan=2, sticky="ew", pady=5)
        self.interval_spinbox = ttk.Spinbox(
            interval_row,
            from_=1,
            to=1440,
            textvariable=self.interval_var,
            width=10,
        )
        self.interval_spinbox.pack(side="left")
        ttk.Label(
            interval_row,
            text="分钟",
            style="Muted.Card.TLabel",
        ).pack(side="left", padx=(8, 0))

        options = ttk.Frame(form_card, style="Card.TFrame")
        options.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 2))
        ttk.Checkbutton(
            options,
            text="开机自动启动",
            variable=self.autostart_var,
        ).pack(side="left")
        ttk.Checkbutton(
            options,
            text="程序启动后自动监控",
            variable=self.start_on_launch_var,
        ).pack(side="left", padx=(18, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 12))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)
        self.start_button = ttk.Button(
            buttons,
            text="开始守护",
            style="Primary.TButton",
            command=self._start_monitoring,
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.check_button = ttk.Button(
            buttons,
            text="立即检测",
            style="Secondary.TButton",
            command=self._check_now,
        )
        self.check_button.grid(row=0, column=1, sticky="ew", padx=5)
        self.stop_button = ttk.Button(
            buttons,
            text="停止",
            style="Secondary.TButton",
            command=self._stop_monitoring,
            state="disabled",
        )
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        log_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 14))
        log_card.pack(fill="both", expand=True)
        log_header = ttk.Frame(log_card, style="Card.TFrame")
        log_header.pack(fill="x", pady=(0, 8))
        ttk.Label(
            log_header,
            text="运行记录（最近 3 小时）",
            style="Section.Card.TLabel",
        ).pack(side="left")
        ttk.Button(
            log_header,
            text="退出",
            style="Ghost.TButton",
            command=self._exit_application,
        ).pack(side="right")
        ttk.Button(
            log_header,
            text="日志目录",
            style="Ghost.TButton",
            command=self._open_log_directory,
        ).pack(side="right", padx=(0, 4))
        ttk.Button(
            log_header,
            text="保存设置",
            style="Ghost.TButton",
            command=self._save_settings,
        ).pack(side="right", padx=(0, 4))

        self.log_text = tk.Text(
            log_card,
            height=8,
            relief="flat",
            borderwidth=0,
            background="#F8FAFC",
            foreground=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            padx=10,
            pady=8,
            wrap="word",
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="最小化或关闭窗口后将在系统托盘继续守护 · 密码使用 DPAPI 加密",
            style="Subtitle.TLabel",
        ).pack(anchor="center", pady=(10, 0))

    @staticmethod
    def _form_label(parent: ttk.Frame, text: str, row: int) -> None:
        ttk.Label(
            parent,
            text=text,
            style="Card.TLabel",
            width=10,
        ).grid(row=row, column=0, sticky="w", pady=5)

    def _read_form(self, validate: bool = True) -> AppConfig:
        try:
            interval = int(self.interval_var.get().strip())
        except ValueError:
            interval = 0
        config = AppConfig(
            username=self.username_var.get(),
            password=self.password_var.get(),
            zone=ZONE_LABELS.get(self.zone_var.get(), ""),
            interval_minutes=interval,
            autostart=self.autostart_var.get(),
            start_on_launch=self.start_on_launch_var.get(),
        )
        if validate:
            config.validate()
        return config

    def _save_settings(self, quiet: bool = False) -> bool:
        try:
            config = self._read_form(validate=True)
            self.store.save(config)
            set_autostart(config.autostart)
            self.config = config
            if not quiet:
                self._append_log("设置已安全保存")
            return True
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法保存", str(exc), parent=self.root)
            return False

    def _start_monitoring(self) -> None:
        if self.monitor.running:
            self.monitor.check_now()
            return
        if not self._save_settings(quiet=True):
            return
        self.monitor.start(self.config)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._append_log(
            f"开始监控，间隔 {self.config.interval_minutes} 分钟"
        )

    def _stop_monitoring(self) -> None:
        if self.monitor.running:
            self.monitor.stop()
        self.stop_button.configure(state="disabled")

    def _check_now(self) -> None:
        if self.monitor.running:
            self.monitor.check_now()
            self._append_log("已请求立即检测")
        else:
            self._start_monitoring()

    def _toggle_password(self) -> None:
        self.password_visible = not self.password_visible
        self.password_entry.configure(show="" if self.password_visible else "●")
        self.show_password_button.configure(
            text="隐藏" if self.password_visible else "显示"
        )

    def _handle_initial_start(self) -> None:
        should_start = self.launched_by_autostart or self.config.start_on_launch
        if self.launched_by_autostart:
            self._hide_to_tray(notify=False)
        if should_start and self.config.username and self.config.password:
            self._start_monitoring()

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                self._apply_event(event)
        except queue.Empty:
            pass
        try:
            while True:
                self._handle_tray_action(self.tray_actions.get_nowait())
        except queue.Empty:
            pass
        if not self.is_exiting:
            self.root.after(150, self._process_events)

    def _apply_event(self, event: MonitorEvent) -> None:
        state_map = {
            "checking": ("检测中", COLORS["primary"]),
            "reconnecting": ("正在重连", COLORS["warning"]),
            "online": ("网络正常", COLORS["success"]),
            "offline": ("网络异常", COLORS["error"]),
            "waiting": ("守护中", COLORS["success"]),
            "stopped": ("已停止", COLORS["idle"]),
        }
        title, color = state_map.get(event.state, ("运行中", COLORS["idle"]))
        self.tray.update(event.state)
        self.status_label.configure(text=title)
        self.status_dot.itemconfigure(self.status_circle, fill=color)
        if event.latency_ms is not None:
            self.detail_label.configure(text=f"{event.latency_ms} ms")
        else:
            self.detail_label.configure(text=event.message)
        if event.state == "stopped":
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
        if event.state == "waiting":
            self.local_log.write(event.message, event.level)
        else:
            self._append_log(event.message, event.level)

    def _append_log(self, message: str, level: str = "info") -> None:
        now = dt.datetime.now()
        self.local_log.write(message, level)
        self.log_entries.append((now, message))
        cutoff = now - UI_LOG_RETENTION
        removed = False
        while self.log_entries and self.log_entries[0][0] < cutoff:
            self.log_entries.popleft()
            removed = True

        self.log_text.configure(state="normal")
        if removed:
            self.log_text.delete("1.0", "end")
            for timestamp, entry in self.log_entries:
                self.log_text.insert("end", f"{timestamp:%H:%M:%S}  {entry}\n")
        else:
            self.log_text.insert("end", f"{now:%H:%M:%S}  {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_unmap(self, _event: tk.Event) -> None:
        self.root.after(80, self._hide_if_iconified)

    def _hide_if_iconified(self) -> None:
        if not self.is_exiting and self.root.state() == "iconic":
            self._hide_to_tray()

    def _hide_to_tray(self, notify: bool = True) -> None:
        if self.is_exiting:
            return
        self.root.withdraw()
        if notify and not self.tray_notice_shown:
            self.tray.notify("程序仍在后台监控，双击托盘图标可打开主界面")
            self.tray_notice_shown = True

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def _handle_tray_action(self, action: str) -> None:
        if action == "show":
            self._show_window()
        elif action == "check":
            self._check_now()
        elif action == "exit":
            self._exit_application()

    def _open_log_directory(self) -> None:
        try:
            self.local_log.open_directory()
        except OSError as exc:
            messagebox.showerror("无法打开日志目录", str(exc), parent=self.root)

    def _on_close(self) -> None:
        self._hide_to_tray()

    def _exit_application(self) -> None:
        if self.is_exiting:
            return
        self.is_exiting = True
        self.local_log.write("程序退出")
        if self.monitor.running:
            self.monitor.stop()
        self.tray.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
