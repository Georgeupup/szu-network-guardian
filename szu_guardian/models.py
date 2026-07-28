from __future__ import annotations

from dataclasses import asdict, dataclass


ZONE_AUTO = "auto"
ZONE_OFFICE = "office"
ZONE_DORMITORY = "dormitory"
VALID_ZONES = {ZONE_AUTO, ZONE_OFFICE, ZONE_DORMITORY}


@dataclass(slots=True)
class AppConfig:
    username: str = ""
    password: str = ""
    zone: str = ZONE_OFFICE
    interval_minutes: int = 5
    autostart: bool = False
    start_on_launch: bool = True

    def validate(self) -> None:
        self.username = self.username.strip()
        if not self.username:
            raise ValueError("请输入校园网账号")
        if not self.password:
            raise ValueError("请输入校园网密码")
        if self.zone not in VALID_ZONES:
            raise ValueError("请选择正确的网络区域")
        try:
            self.interval_minutes = int(self.interval_minutes)
        except (TypeError, ValueError) as exc:
            raise ValueError("监控间隔必须是整数分钟") from exc
        if not 1 <= self.interval_minutes <= 1440:
            raise ValueError("监控间隔应在 1 到 1440 分钟之间")

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("password", None)
        return data
