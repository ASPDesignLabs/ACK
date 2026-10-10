# SPDX-License-Identifier: GPL-3.0-or-later
"""ACK Voice Studio: a guided way to record, train and export a custom voice for ACK, on Ubuntu or WSL.

Plan and decisions: docs/VOICE_STUDIO_SETUP_PLAN.md. This package is being built stage by stage; what exists is listed in that plan's
Progress table. It must run on the system Python of Ubuntu 22.04 (3.10) and 24.04 (3.12), so nothing newer than 3.10 may be used
(tests/test_vs_package_rules.py checks the syntax and the usual newer-only names).
"""

__version__ = "0.0.1"
