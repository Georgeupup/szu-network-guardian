from __future__ import annotations

import threading
from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw


def _icon_image(color: str = "#2563EB") -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=15, fill=color)
    draw.arc((15, 14, 49, 45), 205, 335, fill="white", width=5)
    draw.arc((21, 22, 43, 44), 205, 335, fill="white", width=5)
    draw.ellipse((29, 39, 35, 45), fill="white")
    return image


class TrayController:
    def __init__(self, action_callback: Callable[[str], None]):
        self.action_callback = action_callback
        self.icon = pystray.Icon(
            "szu_network_guardian",
            _icon_image(),
            "SZU 网络守护",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "打开主界面",
                    lambda _icon, _item: self.action_callback("show"),
                    default=True,
                ),
                pystray.MenuItem(
                    "立即检测",
                    lambda _icon, _item: self.action_callback("check"),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "退出程序",
                    lambda _icon, _item: self.action_callback("exit"),
                ),
            ),
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self.icon.run,
            name="szu-tray-icon",
            daemon=True,
        )
        self._thread.start()

    def update(self, state: str) -> None:
        styles = {
            "online": ("#16A34A", "网络正常"),
            "waiting": ("#16A34A", "守护中"),
            "checking": ("#2563EB", "正在检测"),
            "reconnecting": ("#D97706", "正在重连"),
            "offline": ("#DC2626", "网络异常"),
            "stopped": ("#94A3B8", "已停止"),
        }
        color, label = styles.get(state, ("#2563EB", "运行中"))
        self.icon.icon = _icon_image(color)
        self.icon.title = f"SZU 网络守护 - {label}"

    def notify(self, message: str) -> None:
        try:
            self.icon.notify(message, "SZU 网络守护")
        except (NotImplementedError, OSError):
            pass

    def stop(self) -> None:
        self.icon.stop()
