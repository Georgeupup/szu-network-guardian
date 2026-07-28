from __future__ import annotations

import argparse
import ctypes
import sys

from szu_guardian.storage import ConfigStore
from szu_guardian.ui import GuardianApp


def enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SZU 校园网自动重连工具")
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="由 Windows 开机启动项调用；窗口将最小化并自动开始监控",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enable_windows_dpi_awareness()
    app = GuardianApp(ConfigStore(), launched_by_autostart=args.autostart)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
