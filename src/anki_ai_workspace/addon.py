from __future__ import annotations

from aqt import mw
from aqt.qt import QTimer

from .diagnostics import configure_log, logger
from .profile_dialog import show_codex_startup_prompt, show_profile_dialog
from .reviewer import register as register_reviewer

_registered = False


def register() -> None:
    """Register the add-on's Anki UI hooks once per application session."""

    global _registered
    if _registered:
        return
    configure_log(mw.pm.base)
    logger().info("add-on registration started")
    action = mw.form.menuTools.addAction("AI Workspace…")
    action.triggered.connect(show_profile_dialog)
    register_reviewer()
    if not _configured_codex_executable():
        QTimer.singleShot(0, show_codex_startup_prompt)
    _registered = True
    logger().info("add-on registration completed")


def _configured_codex_executable() -> bool:
    config = mw.addonManager.getConfig("anki_ai_workspace") or {}
    return bool(str(config.get("codex_executable") or "").strip())
