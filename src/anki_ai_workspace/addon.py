from __future__ import annotations

from aqt import gui_hooks, mw
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
    gui_hooks.state_did_change.append(_on_initial_main_window_state)
    _registered = True
    logger().info("add-on registration completed")


def _configured_codex_executable() -> bool:
    config = mw.addonManager.getConfig("anki_ai_workspace") or {}
    return bool(str(config.get("codex_executable") or "").strip())


def _on_initial_main_window_state(new_state: str, _old_state: str) -> None:
    """Show onboarding only after Anki has reached its first usable screen."""

    if new_state != "deckBrowser":
        return
    gui_hooks.state_did_change.remove(_on_initial_main_window_state)
    QTimer.singleShot(0, _show_codex_startup_prompt_if_needed)


def _show_codex_startup_prompt_if_needed() -> None:
    config = mw.addonManager.getConfig("anki_ai_workspace") or {}
    if _configured_codex_executable() or config.get("codex_setup_prompt_dismissed"):
        return
    show_codex_startup_prompt()
