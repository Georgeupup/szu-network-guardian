from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Callable

from .models import AppConfig
from .network import NetworkClient


@dataclass(frozen=True, slots=True)
class MonitorEvent:
    state: str
    message: str
    level: str = "info"
    latency_ms: int | None = None


class MonitorController:
    WAIT_SLICE_SECONDS = 15.0
    RESUME_GAP_SECONDS = 30.0

    def __init__(
        self,
        event_callback: Callable[[MonitorEvent], None],
        client_factory: Callable[[], NetworkClient] = NetworkClient,
    ):
        self.event_callback = event_callback
        self.client_factory = client_factory
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, config: AppConfig) -> None:
        with self._lock:
            if self.running:
                self._wake_event.set()
                return
            self._stop_event.clear()
            self._wake_event.clear()
            copied = replace(config)
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(copied,),
                name="szu-network-monitor",
                daemon=True,
            )
            self._thread.start()

    def check_now(self) -> None:
        if self.running:
            self._wake_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)
        else:
            self.event_callback(MonitorEvent("stopped", "监控已停止"))

    def _emit(self, event: MonitorEvent) -> None:
        self.event_callback(event)

    def _run_loop(self, config: AppConfig) -> None:
        client = self.client_factory()
        self._emit(MonitorEvent("checking", "正在检测网络状态…"))

        while not self._stop_event.is_set():
            self._wake_event.clear()
            try:
                result = client.ensure_connected(
                    config,
                    progress_callback=lambda message: self._emit(
                        MonitorEvent("reconnecting", message, "warning")
                    ),
                )
                if result.connected:
                    self._emit(
                        MonitorEvent(
                            "online",
                            result.message,
                            "success",
                            result.latency_ms,
                        )
                    )
                else:
                    self._emit(MonitorEvent("offline", result.message, "warning"))
                    # A sleep/wake cycle or DHCP renewal can invalidate the
                    # bound source address, DNS route, and HTTP sessions.
                    client = self.client_factory()
            except Exception as exc:
                self._emit(
                    MonitorEvent(
                        "offline",
                        f"检测或重连失败：{exc}",
                        "error",
                    )
                )
                client = self.client_factory()

            if self._stop_event.is_set():
                break
            self._emit(
                MonitorEvent(
                    "waiting",
                    f"下次检测将在 {config.interval_minutes} 分钟内进行",
                )
            )
            wait_reason = self._wait_until_next_check(config.interval_minutes * 60)
            if wait_reason == "stop" or self._stop_event.is_set():
                break
            if wait_reason == "resume":
                client = self.client_factory()
                self._emit(
                    MonitorEvent(
                        "checking",
                        "检测到系统从休眠恢复，正在重新建立直连…",
                        "warning",
                    )
                )
            else:
                self._emit(MonitorEvent("checking", "正在检测网络状态…"))
        self._emit(MonitorEvent("stopped", "监控已停止"))

    def _wait_until_next_check(self, interval_seconds: float) -> str:
        """Wait for a manual check, the normal deadline, or a wake-up gap."""
        started = time.time()
        deadline = started + interval_seconds
        while not self._stop_event.is_set():
            remaining = max(0.0, deadline - time.time())
            if remaining == 0:
                return "interval"

            wait_started = time.time()
            if self._wake_event.wait(
                min(self.WAIT_SLICE_SECONDS, remaining)
            ):
                return "manual"

            # Windows may suspend the thread while the Event wait is pending.
            # A wall-clock gap larger than one wait slice indicates that the
            # machine likely resumed; refresh the network client immediately.
            if time.time() - wait_started >= self.RESUME_GAP_SECONDS:
                return "resume"
        return "stop"
