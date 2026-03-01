"""Template for ~/.nuke/init.py — NukeBread bootstrap.

Copy this file (or merge its contents) into your ~/.nuke/init.py so that
Nuke can find the NukeBread package at startup.

Adjust NUKEBREAD_ROOT below to point to your nukebread checkout or
installed package location.
"""

import sys
import os

# -------------------------------------------------------------------
# Set NUKEBREAD_ROOT to the path where nukebread is installed.
# If you pip-installed it into a venv, point to the venv site-packages.
# If running from source, point to the repo's src/ directory.
# -------------------------------------------------------------------
NUKEBREAD_ROOT = os.path.expanduser("~/dev/nukebread/src")

if NUKEBREAD_ROOT not in sys.path:
    sys.path.insert(0, NUKEBREAD_ROOT)

import nuke  # type: ignore[import-not-found]

nuke.pluginAddPath(os.path.join(NUKEBREAD_ROOT, "nukebread", "plugin"))
