# SPDX-License-Identifier: GPL-3.0-or-later
"""Which home-network address this computer has, to tell a phone where to look (plan task VS-5.1, choices P25).

It reads the computer's own list of addresses with the `ip` program (a local question: nothing is sent, nothing is looked up) and keeps only the addresses of a home network that belong to a
real network card. A virtual network that a container or a virtual machine makes on this computer is left out, because a phone cannot be on it. It also says whether this is Ubuntu under
Windows (WSL), because there the address Ubuntu sees is usually one the phone cannot reach (plan task VS-3.6 explains and, with a yes, helps).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple

from . import phonecert, preflight
from .system import System

# `2: eth0    inet 192.168.1.23/24 brd 192.168.1.255 scope global dynamic noprefixroute eth0`
LINE = re.compile(r"^\d+:\s+(\S+)\s+inet\s+(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})\b")
VIRTUAL_PREFIXES = ("lo", "docker", "br-", "veth", "virbr", "cni", "flannel", "lxc", "lxd", "podman", "vboxnet", "vmnet", "tun", "tap")
ERROR_CODES = ()


@dataclass(frozen=True)
class Candidate:
    card: str                                       # the network card's name as the computer calls it (eth0, wlp3s0)
    address: str


def candidates(system: System) -> Tuple[Candidate, ...]:
    """Every home-network address on a real network card, in the order the computer lists them, each once. Empty when `ip` is not there or says nothing."""
    found = system.which("ip")
    if not found:
        return ()
    done = system.run([found, "-4", "-o", "addr", "show", "scope", "global"], timeout=10)
    if done is None or done.returncode != 0:
        return ()
    out, seen = [], set()
    for line in done.stdout.splitlines():
        match = LINE.match(line.strip())
        if not match:
            continue
        card, address = match.group(1).partition("@")[0], match.group(2)
        if card.startswith(VIRTUAL_PREFIXES) or address in seen or not phonecert.is_private_address(address):
            continue
        seen.add(address)
        out.append(Candidate(card, address))
    return tuple(out)


def on_wsl(system: System) -> bool:
    return preflight.detect_platform(system.read_text("/proc/version"), system.environ()) is not preflight.Platform.NATIVE
