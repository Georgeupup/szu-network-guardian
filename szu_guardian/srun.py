"""SRun (深澜) authentication used by SZU teaching/office networks.

The protocol implementation is a Python port of the MIT-licensed
Sleepstars/SZU-login and vidar-team/srun-login projects. See
THIRD_PARTY_NOTICES.md for attribution.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any

import requests


SRUN_BASE_URL = "https://net.szu.edu.cn"
SRUN_ALPHA = "LVoJPiCN2R8G90yg+hmFHuacZ1OWMnrsSTXkYpUq/3dlbfKwv6xztjI7DeBE45QA"
STANDARD_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
UINT32_MASK = 0xFFFFFFFF


def _words(content: bytes, include_length: bool) -> list[int]:
    values = [
        sum(
            (content[index + offset] if index + offset < len(content) else 0)
            << (offset * 8)
            for offset in range(4)
        )
        for index in range(0, len(content), 4)
    ]
    if include_length:
        values.append(len(content))
    return values


def xencode(content: str, key: str) -> bytes:
    """Encode SRun user information with the XXTEA-compatible routine."""
    if not content:
        return b""

    values = _words(content.encode("utf-8"), True)
    key_values = _words(key.encode("utf-8"), False)
    key_values.extend([0] * (4 - len(key_values)))

    n = len(values) - 1
    z = values[n]
    y = values[0]
    delta = 0x9E3779B9
    total = 0
    rounds = 6 + 52 // (n + 1)

    while rounds > 0:
        total = (total + delta) & UINT32_MASK
        e = (total >> 2) & 3
        for p in range(n):
            y = values[p + 1]
            mixed = ((z >> 5) ^ ((y << 2) & UINT32_MASK)) & UINT32_MASK
            mixed = (
                mixed
                + (((y >> 3) ^ ((z << 4) & UINT32_MASK)) ^ (total ^ y))
            ) & UINT32_MASK
            mixed = (mixed + (key_values[(p & 3) ^ e] ^ z)) & UINT32_MASK
            values[p] = (values[p] + mixed) & UINT32_MASK
            z = values[p]

        y = values[0]
        mixed = ((z >> 5) ^ ((y << 2) & UINT32_MASK)) & UINT32_MASK
        mixed = (
            mixed
            + (((y >> 3) ^ ((z << 4) & UINT32_MASK)) ^ (total ^ y))
        ) & UINT32_MASK
        mixed = (mixed + (key_values[(n & 3) ^ e] ^ z)) & UINT32_MASK
        values[n] = (values[n] + mixed) & UINT32_MASK
        z = values[n]
        rounds -= 1

    output = bytearray()
    for value in values:
        output.extend(
            (
                value & 0xFF,
                (value >> 8) & 0xFF,
                (value >> 16) & 0xFF,
                (value >> 24) & 0xFF,
            )
        )
    return bytes(output)


def srun_base64(value: bytes) -> str:
    encoded = base64.b64encode(value).decode("ascii")
    return encoded.translate(str.maketrans(STANDARD_ALPHA, SRUN_ALPHA))


def hmac_md5(password: str, challenge: str) -> str:
    return hmac.new(
        challenge.encode("utf-8"),
        password.encode("utf-8"),
        hashlib.md5,
    ).hexdigest()


def _parse_jsonp(text: str) -> dict[str, Any]:
    match = re.search(r"^[^(]*\((.*)\)\s*;?\s*$", text.strip(), re.DOTALL)
    if not match:
        raise ConnectionError("认证服务器返回了无法识别的数据")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ConnectionError("认证服务器返回了无效 JSON") from exc
    if not isinstance(payload, dict):
        raise ConnectionError("认证服务器响应格式不正确")
    return payload


@dataclass(frozen=True, slots=True)
class SrunLoginResult:
    success: bool
    message: str
    client_ip: str = ""


class SrunClient:
    def __init__(
        self,
        username: str,
        password: str,
        session: requests.Session | None = None,
        base_url: str = SRUN_BASE_URL,
        host_header: str | None = None,
    ):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.host_header = host_header
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                )
            }
        )

    def _get_jsonp(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        headers = {"Host": self.host_header} if self.host_header else None
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=(4, 10),
            verify=False,
            allow_redirects=False,
        )
        response.raise_for_status()
        return _parse_jsonp(response.text)

    def discover_ac_id(self) -> str:
        headers = {"Host": self.host_header} if self.host_header else None
        try:
            response = self.session.get(
                f"{self.base_url}/",
                headers=headers,
                timeout=(3, 7),
                verify=False,
                allow_redirects=not bool(self.host_header),
            )
            search_text = response.text + " " + response.headers.get("Location", "")
            match = re.search(r"ac_id=(\d+)", search_text)
            if match:
                return match.group(1)
            if self.host_header:
                response = self.session.get(
                    f"{self.base_url}/index_1.html",
                    headers=headers,
                    timeout=(3, 7),
                    verify=False,
                    allow_redirects=False,
                )
                match = re.search(r"ac_id=(\d+)", response.text)
                if match:
                    return match.group(1)
        except requests.RequestException:
            pass
        return "1"

    def login(self) -> SrunLoginResult:
        ac_id = self.discover_ac_id()
        challenge_data = self._get_jsonp(
            "/cgi-bin/get_challenge",
            {"callback": "_", "username": self.username, "ip": ""},
        )
        if challenge_data.get("error") not in ("ok", None, ""):
            message = str(
                challenge_data.get("error_msg")
                or challenge_data.get("error")
                or "获取认证挑战失败"
            )
            return SrunLoginResult(False, message)

        challenge = str(challenge_data.get("challenge", ""))
        client_ip = str(challenge_data.get("client_ip", ""))
        if not challenge or not client_ip:
            return SrunLoginResult(False, "认证服务器未返回 challenge 或客户端 IP")

        password_md5 = hmac_md5(self.password, challenge)
        info_json = json.dumps(
            {
                "username": self.username,
                "password": self.password,
                "ip": client_ip,
                "acid": ac_id,
                "enc_ver": "srun_bx1",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        info = "{SRBX1}" + srun_base64(xencode(info_json, challenge))
        checksum_source = "".join(
            challenge + field
            for field in (
                self.username,
                password_md5,
                ac_id,
                client_ip,
                "200",
                "1",
                info,
            )
        )
        checksum = hashlib.sha1(checksum_source.encode("utf-8")).hexdigest()

        portal_data = self._get_jsonp(
            "/cgi-bin/srun_portal",
            {
                "callback": "_",
                "action": "login",
                "username": self.username,
                "password": "{MD5}" + password_md5,
                "os": "Windows",
                "name": "Windows",
                "double_stack": "0",
                "info": info,
                "chksum": checksum,
                "ac_id": ac_id,
                "ip": client_ip,
                "n": "200",
                "type": "1",
            },
        )
        success = (
            portal_data.get("error") == "ok"
            or portal_data.get("res") == "ok"
            or portal_data.get("st") == 1
        )
        if success:
            return SrunLoginResult(True, "教学 / 办公区认证成功", client_ip)

        message = str(
            portal_data.get("error_msg")
            or portal_data.get("error")
            or portal_data.get("res")
            or "认证失败"
        )
        return SrunLoginResult(False, message, client_ip)
