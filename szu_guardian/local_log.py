from __future__ import annotations

import datetime as dt
import os
import threading
from pathlib import Path

from .storage import default_config_path


LOG_RETENTION_DAYS = 7


def default_log_directory() -> Path:
    return default_config_path().parent / "logs"


class LocalLog:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or default_log_directory()
        self._lock = threading.Lock()
        self._last_cleanup: dt.datetime | None = None
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cleanup()

    def write(self, message: str, level: str = "info") -> None:
        now = dt.datetime.now()
        safe_message = " ".join(str(message).splitlines())
        line = f"{now:%Y-%m-%d %H:%M:%S} [{level.upper()}] {safe_message}\n"
        path = self.directory / f"guardian-{now:%Y-%m-%d}.log"
        with self._lock:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(line)
            if (
                self._last_cleanup is None
                or now - self._last_cleanup >= dt.timedelta(hours=1)
            ):
                self.cleanup(now)

    def cleanup(self, now: dt.datetime | None = None) -> None:
        now = now or dt.datetime.now()
        cutoff = now.date() - dt.timedelta(days=LOG_RETENTION_DAYS)
        for path in self.directory.glob("guardian-*.log"):
            try:
                file_date = dt.date.fromisoformat(path.stem.removeprefix("guardian-"))
                if file_date < cutoff:
                    path.unlink()
            except (OSError, ValueError):
                continue
        self._last_cleanup = now

    def open_directory(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(self.directory)  # type: ignore[attr-defined]
        else:
            raise OSError("打开日志目录目前仅支持 Windows")
