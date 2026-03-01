"""UI-only helper constructors for consistent visual styling."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton


def section_header(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "sectionHeader")
    return label


def card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def _apply_variant(button: QPushButton, variant: str) -> None:
    button.setProperty("variant", variant)
    button.style().unpolish(button)
    button.style().polish(button)


def set_primary(button: QPushButton) -> None:
    _apply_variant(button, "primary")


def set_secondary(button: QPushButton) -> None:
    _apply_variant(button, "secondary")


def set_danger(button: QPushButton) -> None:
    _apply_variant(button, "danger")
