from __future__ import annotations

import unittest

from anki_ai_workspace.reviewer_protocol import parse_message


class ReviewerProtocolTests(unittest.TestCase):
    def test_parses_structured_send_message(self) -> None:
        payload = parse_message('anki-ai-workspace:{"action":"send","message":"hello"}')

        self.assertEqual(payload, {"action": "send", "message": "hello"})

    def test_rejects_malformed_or_unknown_messages(self) -> None:
        self.assertIsNone(parse_message("anki-ai-workspace:not-json"))
        self.assertIsNone(parse_message('anki-ai-workspace:{"action":"open-settings"}'))
        self.assertIsNone(parse_message("other-command"))

    def test_parses_profile_menu_actions(self) -> None:
        self.assertEqual(
            parse_message(
                'anki-ai-workspace:{"action":"select_action","action_id":"action-1"}'
            ),
            {"action": "select_action", "action_id": "action-1"},
        )
        self.assertEqual(
            parse_message('anki-ai-workspace:{"action":"open_custom"}'),
            {"action": "open_custom"},
        )

    def test_parses_session_selector_action(self) -> None:
        self.assertEqual(
            parse_message(
                'anki-ai-workspace:{"action":"select_session","conversation_id":"card:42"}'
            ),
            {"action": "select_session", "conversation_id": "card:42"},
        )

    def test_parses_workspace_management_actions(self) -> None:
        self.assertEqual(
            parse_message('anki-ai-workspace:{"action":"open_deck_general"}'),
            {"action": "open_deck_general"},
        )
        self.assertEqual(
            parse_message('anki-ai-workspace:{"action":"close_workspace"}'),
            {"action": "close_workspace"},
        )
        self.assertEqual(
            parse_message('anki-ai-workspace:{"action":"save_scroll"}'),
            {"action": "save_scroll"},
        )
        self.assertEqual(
            parse_message('anki-ai-workspace:{"action":"configure_codex"}'),
            {"action": "configure_codex"},
        )
