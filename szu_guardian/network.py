from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import requests
import urllib3

from .models import (
    AppConfig,
    ZONE_AUTO,
    ZONE_DORMITORY,
    ZONE_OFFICE,
)
from .srun import SrunClient


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DORMITORY_LOGIN_URL = "http://172.30.255.42:801/eportal/portal/login/"

CHECK_TARGETS = (
    ("https://www.baidu.com/favicon.ico", "baidu"),
    ("http://www.msftconnecttest.com/connecttest.txt", "Microsoft Connect Test"),
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    connected: bool
    message: str
    latency_ms: int | None = None


def _new_direct_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(HEADERS)
    return session


def _parse_jsonp_object(text: str) -> dict[str, object]:
    match = re.search(r"^[^(]*\((.*)\)\s*;?\s*$", text.strip(), re.DOTALL)
    if not match:
        raise ConnectionError("宿舍区认证服务器返回了无法识别的数据")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ConnectionError("宿舍区认证服务器返回了无效 JSON") from exc
    if not isinstance(payload, dict):
        raise ConnectionError("宿舍区认证响应格式不正确")
    return payload


class NetworkClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        portal_session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        verify_delays: tuple[float, ...] = (2.0, 4.0, 8.0),
    ):
        self.session = session or _new_direct_session()
        self.portal_session = portal_session or (
            session if session is not None else _new_direct_session()
        )
        for active_session in {id(self.session): self.session, id(self.portal_session): self.portal_session}.values():
            active_session.trust_env = False
            active_session.headers.update(HEADERS)
        self.sleeper = sleeper
        self.verify_delays = verify_delays

    def check_connection(self) -> ConnectionResult:
        started = time.perf_counter()
        errors: list[str] = []

        for url, expected in CHECK_TARGETS:
            try:
                response = self.session.get(
                    url,
                    timeout=(3, 5),
                    allow_redirects=True,
                )
                if expected == "baidu":
                    final_host = urlparse(response.url).hostname or ""
                    valid = response.status_code == 200 and final_host.endswith("baidu.com")
                else:
                    valid = (
                        response.status_code == 200
                        and expected in response.text
                    )
                if valid:
                    latency = round((time.perf_counter() - started) * 1000)
                    return ConnectionResult(True, "网络连接正常", latency)
                errors.append(f"检测页返回 {response.status_code}")
            except requests.RequestException as exc:
                errors.append(type(exc).__name__)

        detail = " / ".join(errors[-2:]) if errors else "无响应"
        return ConnectionResult(False, f"直连外网不可用（{detail}）")

    def _login_dormitory(self, config: AppConfig) -> str:
        response = self.portal_session.get(
            DORMITORY_LOGIN_URL,
            params={
                "user_account": config.username,
                "user_password": config.password,
            },
            timeout=(4, 10),
            allow_redirects=True,
        )
        response.raise_for_status()
        payload = _parse_jsonp_object(response.text)
        message = str(payload.get("msg", "")).strip()
        success = (
            payload.get("result") in (1, "1", True)
            or "success" in message.lower()
            or "成功" in message
        )
        if not success:
            raise ConnectionError(message or "宿舍区认证失败，请检查账号和密码")
        return message or "宿舍区认证成功"

    def _login_teaching(self, config: AppConfig) -> str:
        result = SrunClient(
            config.username,
            config.password,
            session=self.portal_session,
        ).login()
        if not result.success:
            raise ConnectionError(
                f"教学 / 办公区认证失败：{result.message or '请检查账号和密码'}"
            )
        return result.message

    def send_login(
        self,
        config: AppConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        zone = config.zone
        if zone == ZONE_AUTO:
            errors: list[str] = []
            attempts = (
                ("教学 / 办公区", self._login_teaching),
                ("宿舍区", self._login_dormitory),
            )
            for zone_name, login in attempts:
                if progress_callback:
                    progress_callback(f"自动尝试：正在使用{zone_name}认证…")
                try:
                    return login(config)
                except (ConnectionError, requests.RequestException) as exc:
                    errors.append(f"{zone_name}：{exc}")
            details = "；".join(errors)
            raise ConnectionError(
                f"自动尝试均未成功，请手动选择实际区域。{details}"
            )

        if progress_callback:
            zone_name = "宿舍区" if zone == ZONE_DORMITORY else "教学 / 办公区"
            progress_callback(f"正在使用{zone_name}认证…")

        if zone == ZONE_DORMITORY:
            return self._login_dormitory(config)
        if zone == ZONE_OFFICE:
            return self._login_teaching(config)
        raise ConnectionError("无法确定校园网区域")

    def ensure_connected(
        self,
        config: AppConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> ConnectionResult:
        current = self.check_connection()
        if current.connected:
            return current

        login_message = self.send_login(config, progress_callback)
        if progress_callback:
            progress_callback(f"{login_message}，正在等待外网恢复…")

        for attempt, delay in enumerate(self.verify_delays, start=1):
            self.sleeper(delay)
            verified = self.check_connection()
            if verified.connected:
                return ConnectionResult(
                    True,
                    "已自动重连，网络恢复正常",
                    verified.latency_ms,
                )
            if progress_callback and attempt < len(self.verify_delays):
                progress_callback(
                    f"外网尚未恢复，{self.verify_delays[attempt]:g} 秒后再次复查…"
                )

        return ConnectionResult(
            False,
            "认证服务器已确认请求，但外网仍不可用；请查看本地日志中的认证结果",
        )
