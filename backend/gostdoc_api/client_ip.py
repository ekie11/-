"""Определение IP клиента с учётом доверенных прокси."""

from __future__ import annotations

import ipaddress

from fastapi import Request


def _parse(value: str):
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _networks(trusted: tuple[str, ...]):
    nets = []
    for item in trusted:
        try:
            nets.append(ipaddress.ip_network(item.strip(), strict=False))
        except ValueError:
            continue
    return nets


def _in(addr, nets) -> bool:
    return any(addr.version == n.version and addr in n for n in nets)


def client_ip(request: Request, trusted: tuple[str, ...]) -> str:
    """Адрес клиента.

    X-Forwarded-For учитывается только если прямой адрес подключения доверенный;
    тогда берётся первый справа недоверенный адрес. Некорректная запись — адрес
    подключения.
    """
    peer = request.client.host if request.client else ""
    nets = _networks(trusted)
    peer_addr = _parse(peer)
    if not nets or peer_addr is None or not _in(peer_addr, nets):
        return peer
    header = ",".join(request.headers.getlist("x-forwarded-for"))
    if not header:
        return peer
    for raw in reversed(header.split(",")):
        addr = _parse(raw)
        if addr is None:
            return peer
        if not _in(addr, nets):
            return str(addr)
    return peer
