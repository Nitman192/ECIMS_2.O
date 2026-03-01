"""Idle lock manager using Qt event filter and timer."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer


class IdleLockManager(QObject):
    """Automatically invokes lock callback after inactivity."""

    def __init__(self, idle_seconds: int, lock_callback, status_callback):
        super().__init__()
        self.idle_seconds = idle_seconds
        self.lock_callback = lock_callback
        self.status_callback = status_callback
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timeout)

    def start(self) -> None:
        if self.idle_seconds <= 0:
            return
        self.timer.start(self.idle_seconds * 1000)

    def eventFilter(self, _obj, event):  # noqa: N802
        if self.idle_seconds > 0 and event.type() in {
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
        }:
            self.timer.start(self.idle_seconds * 1000)
        return False

    def _on_timeout(self) -> None:
        self.lock_callback()
        self.status_callback("Idle timeout reached: key material locked.")
        self.timer.start(self.idle_seconds * 1000)
