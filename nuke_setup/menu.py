"""Template for ~/.nuke/menu.py — NukeBread menu registration.

Copy this file (or merge its contents) into your ~/.nuke/menu.py.
Requires that init.py has already added NukeBread to sys.path.
"""

import nukebread.plugin.menu

nukebread.plugin.menu.register()

# Uncomment the line below to auto-start the bridge server on Nuke launch:
# nukebread.plugin.menu._start_bridge()
