from __future__ import annotations

import json

COMMAND_PREFIX = "anki-ai-workspace:"
VALID_ACTIONS = {
    "toggle",
    "toggle_menu",
    "open_custom",
    "open_deck_general",
    "select_action",
    "configure_profiles",
    "configure_codex",
    "sync",
    "minimize",
    "close_workspace",
    "restore_workspace",
    "send",
    "cancel",
    "retry",
    "copy_diagnostic",
    "save_layout",
    "save_scroll",
    "reset_layout",
    "select_session",
}


def parse_message(message: str) -> dict[str, object] | None:
    if not message.startswith(COMMAND_PREFIX):
        return None
    try:
        payload = json.loads(message[len(COMMAND_PREFIX) :])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("action") not in VALID_ACTIONS:
        return None
    if not isinstance(payload["action"], str):
        return None
    return payload
