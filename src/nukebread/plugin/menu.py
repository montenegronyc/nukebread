"""Nuke menu registration for NukeBread."""

from __future__ import annotations


def register() -> None:
    """Add NukeBread menu items to Nuke's menu bar.

    Call from ~/.nuke/menu.py after Nuke has finished loading.
    """
    import nuke  # type: ignore[import-not-found]
    from nukebread.plugin.panel import register_panel

    # Register the panel widget so it appears in Windows > Custom
    register_panel()

    menubar = nuke.menu("Nuke")
    nb_menu = menubar.addMenu("NukeBread")

    nb_menu.addCommand("Open Panel", _open_panel, "alt+shift+n")
    nb_menu.addCommand("Start Bridge", _start_bridge)
    nb_menu.addCommand("Stop Bridge", _stop_bridge)


def _open_panel() -> None:
    """Show the NukeBread chat panel via nukescripts' panel system."""
    try:
        import nukescripts  # type: ignore[import-not-found]
        nukescripts.panels.restorePanel("com.nukebread.panel")
    except Exception:
        from nukebread.plugin.panel import NukeBreadPanel
        panel = NukeBreadPanel()
        panel.show()


def _start_bridge() -> None:
    """Start the NukeBread bridge server inside Nuke."""
    import nukebread.plugin
    nukebread.plugin.start()


def _stop_bridge() -> None:
    """Stop the NukeBread bridge server."""
    import nukebread.plugin
    nukebread.plugin.stop()
