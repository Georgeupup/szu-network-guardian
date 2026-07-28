from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path

from .models import AppConfig, ZONE_AUTO


APP_DIRECTORY = "SZUNetworkGuardian"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob_from_bytes(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data, max(1, len(data)))
    blob = DATA_BLOB(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer


def protect_secret(secret: str) -> str:
    if not secret:
        return ""
    if sys.platform != "win32":
        raise OSError("安全保存密码仅支持 Windows")

    raw = secret.encode("utf-8")
    input_blob, input_buffer = _blob_from_bytes(raw)
    output_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    description = "SZU Network Guardian"

    ok = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    _ = input_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        protected = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(output_blob.pbData)


def unprotect_secret(encoded: str) -> str:
    if not encoded:
        return ""
    if sys.platform != "win32":
        return ""

    protected = base64.b64decode(encoded)
    input_blob, input_buffer = _blob_from_bytes(protected)
    output_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    _ = input_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        raw = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return raw.decode("utf-8")
    finally:
        kernel32.LocalFree(output_blob.pbData)


def default_config_path() -> Path:
    override = os.environ.get("SZU_GUARDIAN_DATA_DIR")
    if override:
        return Path(override) / "config.json"
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIRECTORY / "config.json"
    return Path.home() / f".{APP_DIRECTORY}" / "config.json"


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            password = unprotect_secret(str(payload.get("password_dpapi", "")))
            schema_version = int(payload.get("schema_version", 1))
            zone = str(payload.get("zone", ZONE_AUTO))
            if schema_version < 2:
                zone = ZONE_AUTO
            return AppConfig(
                username=str(payload.get("username", "")),
                password=password,
                zone=zone,
                interval_minutes=int(payload.get("interval_minutes", 5)),
                autostart=bool(payload.get("autostart", False)),
                start_on_launch=bool(payload.get("start_on_launch", True)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = config.public_dict()
        payload["schema_version"] = 2
        payload["password_dpapi"] = protect_secret(config.password)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
