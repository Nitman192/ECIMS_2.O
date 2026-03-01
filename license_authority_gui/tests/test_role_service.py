"""Tests for UI role permission decisions."""

from __future__ import annotations

from la_gui.ui.role_service import ROLE_ADMIN, ROLE_AUDITOR, ROLE_OPERATOR, can_perform


def test_admin_allows_destructive() -> None:
    assert can_perform(ROLE_ADMIN, "root.generate").allowed


def test_operator_blocks_destructive_subset() -> None:
    assert not can_perform(ROLE_OPERATOR, "root.generate").allowed
    assert can_perform(ROLE_OPERATOR, "license.sign").allowed


def test_auditor_is_read_only() -> None:
    assert not can_perform(ROLE_AUDITOR, "license.sign").allowed
    assert can_perform(ROLE_AUDITOR, "audit.verify").allowed
