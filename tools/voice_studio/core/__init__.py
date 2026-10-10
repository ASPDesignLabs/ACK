# SPDX-License-Identifier: GPL-3.0-or-later
"""Everything the window decides, in plain Python.

The rule (the one capture/ and core/ follow in the Android app): nothing in this folder imports a GUI toolkit, so a plain Python test
run covers it without a display. Network access is not allowed here either; the only module that may touch the network is the
download module (plan task VS-1.3). tests/test_vs_package_rules.py holds both rules.
"""
