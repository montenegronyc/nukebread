"""PySide6 status panel for NukeBread inside Nuke 17.

Shows bridge connection status and logs tool calls made by Claude Code
via the MCP server. The user drives the session from the Claude Code
terminal — this panel is a read-only companion view.
"""

from __future__ import annotations

from PySide6 import QtWidgets, QtCore


class NukeBreadPanel(QtWidgets.QWidget):
    """Status panel that lives inside Nuke's panel system."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("NukeBread")
        self.setMinimumWidth(360)
        self.setMinimumHeight(400)
        self._build_ui()

        # Poll bridge status every 2 seconds
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._check_bridge_status)
        self._status_timer.start(2000)
        self._check_bridge_status()

    # --- UI construction ---

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Status bar
        self._status = QtWidgets.QLabel("Bridge: checking...")
        self._status.setStyleSheet(
            "color: #aaa; font-size: 11px; padding: 2px 4px;"
        )
        layout.addWidget(self._status)

        # Hint label
        hint = QtWidgets.QLabel("Chat with NukeBread in your Claude Code terminal.")
        hint.setStyleSheet("color: #777; font-size: 11px; padding: 2px 4px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Activity log
        self._log = QtWidgets.QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "QTextEdit { background: #1a1a1a; color: #ddd; "
            "font-family: monospace; font-size: 12px; }"
        )
        layout.addWidget(self._log, stretch=1)

        # Clear button
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._clear_btn = QtWidgets.QPushButton("Clear Log")
        self._clear_btn.setFixedWidth(80)
        self._clear_btn.clicked.connect(self._log.clear)
        btn_row.addWidget(self._clear_btn)
        layout.addLayout(btn_row)

    # --- Public API ---

    def log(self, text: str, color: str = "#ddd") -> None:
        """Append a line to the activity log."""
        self._log.append(f'<span style="color:{color};">{text}</span>')
        scrollbar = self._log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_status(self, connected: bool) -> None:
        if connected:
            self._status.setText("Bridge: connected")
            self._status.setStyleSheet(
                "color: #6c6; font-size: 11px; padding: 2px 4px;"
            )
        else:
            self._status.setText("Bridge: disconnected")
            self._status.setStyleSheet(
                "color: #aaa; font-size: 11px; padding: 2px 4px;"
            )

    # --- Slots ---

    @QtCore.Slot()
    def _check_bridge_status(self) -> None:
        import nukebread.plugin as plugin
        self.set_status(plugin._bridge is not None)


def register_panel() -> None:
    """Register NukeBread as a dockable panel in Nuke's panel system."""
    try:
        import nukescripts  # type: ignore[import-not-found]

        nukescripts.registerWidgetAsPanel(
            "nukebread.plugin.panel.NukeBreadPanel",
            "NukeBread",
            "com.nukebread.panel",
        )
    except ImportError:
        pass
