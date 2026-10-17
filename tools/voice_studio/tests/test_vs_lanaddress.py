# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the computer's home-network address (plan task VS-5.1, choices P25): which addresses count, which network cards are left out, and what is said when `ip` is not there."""
import pytest

from vs_fakes import PROC_NATIVE, PROC_WSL1, PROC_WSL2, FakeSystem
from voice_studio.core import lanaddress as la
from voice_studio.core.system import CommandResult

DESKTOP = """2: wlp3s0    inet 192.168.1.23/24 brd 192.168.1.255 scope global dynamic noprefixroute wlp3s0\\       valid_lft 85234sec preferred_lft 85234sec
3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever
4: virbr0    inet 192.168.122.1/24 brd 192.168.122.255 scope global virbr0\\       valid_lft forever preferred_lft forever
"""


class IpSystem(FakeSystem):
    def __init__(self, output=None, result=None, has_ip=True, **kw):
        super().__init__(**kw)
        self.output, self.result, self.has_ip = output, result, has_ip
        self.timeouts = []

    def which(self, name):
        return ("/usr/sbin/ip" if self.has_ip else None) if name == "ip" else super().which(name)

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        if argv[0].endswith("/ip"):
            self.ran.append(tuple(argv))
            self.timeouts.append(timeout)
            return self.result if self.result is not None or self.output is None else CommandResult(0, self.output)
        return super().run(argv, timeout, cwd, env)


def got(output, **kw):
    return la.candidates(IpSystem(output, **kw))


def test_a_desktop_with_a_wifi_card_a_container_network_and_a_virtual_machine_network_has_one_address():
    assert got(DESKTOP) == (la.Candidate("wlp3s0", "192.168.1.23"),)


def test_the_question_asked_is_a_local_one_for_global_addresses_only():
    system = IpSystem(DESKTOP)
    la.candidates(system)
    assert system.ran == [("/usr/sbin/ip", "-4", "-o", "addr", "show", "scope", "global")] and system.timeouts == [10]


def test_two_real_cards_give_two_addresses_in_the_order_listed():
    out = "2: eno1    inet 10.0.0.5/24 brd 10.0.0.255 scope global eno1\\ x\n3: wlp3s0    inet 192.168.0.9/24 brd 192.168.0.255 scope global wlp3s0\\ x\n"
    assert got(out) == (la.Candidate("eno1", "10.0.0.5"), la.Candidate("wlp3s0", "192.168.0.9"))


def test_an_address_that_is_not_a_home_network_address_is_left_out():
    out = ("2: eth0    inet 203.0.113.5/24 scope global eth0\\ x\n3: eth1    inet 172.32.0.1/16 scope global eth1\\ x\n4: eth2    inet 100.64.0.9/10 scope global eth2\\ x\n"
           "5: eth3    inet 172.16.0.2/12 scope global eth3\\ x\n")
    assert got(out) == (la.Candidate("eth3", "172.16.0.2"),)


@pytest.mark.parametrize("card", ["lo", "docker0", "br-1a2b3c", "veth12ab", "virbr0", "cni0", "flannel.1", "lxcbr0", "lxdbr0", "podman0", "vboxnet0", "vmnet8", "tun0", "tap0"])
def test_a_virtual_network_card_is_left_out(card):
    assert got("2: %s    inet 192.168.9.1/24 scope global %s\\ x\n" % (card, card)) == ()


@pytest.mark.parametrize("card", ["eth0", "wlan0", "enp5s0", "wlp3s0", "eno1", "ens33", "wlx00e04c", "bond0", "vlan10", "enx001122"])
def test_a_real_network_card_is_kept(card):
    assert got("2: %s    inet 192.168.9.1/24 scope global %s\\ x\n" % (card, card)) == (la.Candidate(card, "192.168.9.1"),)


def test_the_same_address_on_two_lines_is_listed_once_and_a_card_alias_is_cut_off():
    out = "2: eth0    inet 192.168.1.5/24 scope global eth0\\ x\n2: eth0    inet 192.168.1.5/24 scope global secondary eth0\\ x\n3: eth1@if7    inet 192.168.1.6/24 scope global eth1\\ x\n"
    assert got(out) == (la.Candidate("eth0", "192.168.1.5"), la.Candidate("eth1", "192.168.1.6"))


@pytest.mark.parametrize("line", ["", "garbage", "2: eth0    inet6 fe80::1/64 scope link", "2: eth0    inet 192.168.1/24 scope global", "eth0 inet 192.168.1.5/24", "2: eth0 inet 192.168.1.5 scope global",
                                  "2: eth0    inet 192.168.1.256/24 scope global eth0\\ x", "x2: eth0    inet 192.168.1.5/24 scope global eth0\\ x"])
def test_a_line_that_is_not_an_address_line_is_ignored(line):
    assert got(line + "\n") == ()


def test_a_line_that_is_not_an_address_line_does_not_stop_the_ones_after_it():
    out = "garbage\n2: eth0    inet6 fe80::1/64 scope link\n3: eth1    inet 192.168.1.5/24 scope global eth1\\ x\n"
    assert got(out) == (la.Candidate("eth1", "192.168.1.5"),)
    assert got("2: docker0    inet 192.168.9.1/24 scope global docker0\\ x\n3: eth1    inet 192.168.1.5/24 scope global eth1\\ x\n") == (la.Candidate("eth1", "192.168.1.5"),), "a skipped card does not end the list"


def test_without_ip_or_when_it_fails_there_are_no_addresses_and_no_crash():
    assert got(DESKTOP, has_ip=False) == ()
    assert la.candidates(IpSystem(result=CommandResult(1, DESKTOP))) == ()
    assert la.candidates(IpSystem(output="")) == ()
    system = IpSystem()
    system.output, system.result = "x", None
    system.run = lambda argv, timeout=15.0, cwd=None, env=None: None
    assert la.candidates(system) == ()


def test_ubuntu_under_windows_is_recognised_by_its_kernel_or_its_environment():
    assert la.on_wsl(FakeSystem(proc_version=PROC_WSL2)) and la.on_wsl(FakeSystem(proc_version=PROC_WSL1))
    assert la.on_wsl(FakeSystem(proc_version=None, environ={"WSL_DISTRO_NAME": "Ubuntu"}))
    assert not la.on_wsl(FakeSystem(proc_version=PROC_NATIVE, environ={}))
