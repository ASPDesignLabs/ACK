# SPDX-License-Identifier: GPL-3.0-or-later
"""The window (plan tasks VS-2.1 and VS-0.1): a thin GTK 4.6 edge over core/windowmodel.py and core/windowio.py, which hold every decision and are tested without GTK.

Rules this package keeps (plan section 3, P6): GTK 4.6 API only (that is Ubuntu 22.04's; newer calls such as Gtk.FileDialog or Gtk.AlertDialog would stop the window on the machine
it is for); every control has an accessible name; text is 12 pt or larger and follows the system's text size; no sound and no animation other than a progress bar; nothing starts without a
click; every change goes through the same flow the terminal runs, which shows what it will do and asks first.

Run it with the system Python (the one Ubuntu's python3-gi belongs to), not a virtual environment: `PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window`.
"""
