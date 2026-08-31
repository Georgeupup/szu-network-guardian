from __future__ import annotations

import ipaddress
import random
import socket
import struct
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager


FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")
PREFERRED_CAMPUS_NETWORK = ipaddress.ip_network("172.30.0.0/16")
DIRECT_DNS_SERVERS = ("223.5.5.5", "119.29.29.29", "114.114.114.114")


class DirectNetworkError(ConnectionError):
    pass


def _skip_dns_name(packet: bytes, offset: int) -> int:
    while offset < len(packet):
        length = packet[offset]
        if length & 0xC0 == 0xC0:
            return offset + 2
        if length == 0:
            return offset + 1
        offset += length + 1
    raise DirectNetworkError("直连 DNS 返回了无效数据")


def query_a_record(
    hostname: str,
    dns_server: str,
    source_ip: str,
    timeout: float = 2.0,
) -> list[str]:
    transaction_id = random.randint(0, 0xFFFF)
    labels = hostname.rstrip(".").split(".")
    question_name = b"".join(
        bytes((len(label.encode("idna")),)) + label.encode("idna")
        for label in labels
    ) + b"\x00"
    packet = (
        struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
        + question_name
        + struct.pack("!HH", 1, 1)
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.bind((source_ip, 0))
        sock.sendto(packet, (dns_server, 53))
        response, _ = sock.recvfrom(4096)
    finally:
        sock.close()

    if len(response) < 12:
        raise DirectNetworkError("直连 DNS 响应过短")
    response_id, flags, question_count, answer_count, authority_count, extra_count = (
        struct.unpack("!HHHHHH", response[:12])
    )
    if response_id != transaction_id or flags & 0x000F:
        raise DirectNetworkError("直连 DNS 查询失败")

    offset = 12
    for _ in range(question_count):
        offset = _skip_dns_name(response, offset) + 4

    addresses: list[str] = []
    for _ in range(answer_count + authority_count + extra_count):
        offset = _skip_dns_name(response, offset)
        if offset + 10 > len(response):
            break
        record_type, record_class, _ttl, length = struct.unpack(
            "!HHIH", response[offset : offset + 10]
        )
        offset += 10
        value = response[offset : offset + length]
        offset += length
        if record_type == 1 and record_class == 1 and length == 4:
            address = socket.inet_ntoa(value)
            if ipaddress.ip_address(address) not in FAKE_IP_NETWORK:
                addresses.append(address)
    return list(dict.fromkeys(addresses))


def local_ipv4_candidates() -> list[str]:
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    except socket.gaierror as exc:
        raise DirectNetworkError("无法读取本机网卡地址") from exc

    valid: list[str] = []
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            continue
        if (
            parsed.version == 4
            and parsed.is_private
            and not parsed.is_loopback
            and not parsed.is_link_local
            and parsed not in FAKE_IP_NETWORK
        ):
            valid.append(address)
    valid.sort(
        key=lambda value: ipaddress.ip_address(value) not in PREFERRED_CAMPUS_NETWORK
    )
    return valid


class SourceAddressAdapter(HTTPAdapter):
    def __init__(self, source_ip: str, *args, **kwargs):
        self.source_ip = source_ip
        super().__init__(*args, **kwargs)

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs,
    ) -> None:
        pool_kwargs["source_address"] = (self.source_ip, 0)
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )


def create_bound_session(source_ip: str) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.mount("http://", SourceAddressAdapter(source_ip))
    session.mount("https://", SourceAddressAdapter(source_ip))
    return session


@dataclass(slots=True)
class DirectRoute:
    source_ip: str
    dns_servers: tuple[str, ...] = DIRECT_DNS_SERVERS
    _cache: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def discover(cls) -> "DirectRoute":
        candidates = local_ipv4_candidates()
        if not candidates:
            raise DirectNetworkError(
                "未找到校园网物理网卡；请确认已连接校园有线网络或 SZU_WLAN"
            )

        for source_ip in candidates:
            route = cls(source_ip)
            try:
                route.resolve("net.szu.edu.cn")
                return route
            except DirectNetworkError:
                continue
        raise DirectNetworkError(
            "无法通过物理网卡进行直连 DNS 查询；请检查校园网连接"
        )

    def resolve(self, hostname: str) -> list[str]:
        if hostname in self._cache:
            return self._cache[hostname]
        errors: list[str] = []
        for server in self.dns_servers:
            try:
                addresses = query_a_record(hostname, server, self.source_ip)
                if addresses:
                    self._cache[hostname] = addresses
                    return addresses
            except (OSError, DirectNetworkError) as exc:
                errors.append(type(exc).__name__)
        detail = "/".join(errors) or "无 A 记录"
        raise DirectNetworkError(f"无法直连解析 {hostname}（{detail}）")

    def session(self) -> requests.Session:
        return create_bound_session(self.source_ip)

    def rewrite_url(self, url: str) -> tuple[str, str]:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            raise DirectNetworkError(f"无效的检测地址：{url}")
        try:
            ipaddress.ip_address(hostname)
            return url, hostname
        except ValueError:
            pass

        address = self.resolve(hostname)[0]
        port = f":{parsed.port}" if parsed.port else ""
        rewritten = urlunsplit(
            (parsed.scheme, f"{address}{port}", parsed.path, parsed.query, parsed.fragment)
        )
        return rewritten, hostname
