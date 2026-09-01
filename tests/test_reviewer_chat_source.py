from pathlib import Path
import unittest

SOURCE_PATH = (
    Path(__file__).parents[1] / "src" / "anki_ai_workspace" / "reviewer_chat.py"
)


class ReviewerChatSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_workspace_uses_typed_conversation_identities(self) -> None:
        self.assertIn("self._sessions: dict[str, ChatSession]", self.source)
        self.assertIn('f"card:{card_id}"', self.source)
        self.assertIn('f"deck:{deck_id}"', self.source)

    def test_preset_actions_target_current_card_conversation(self) -> None:
        self.assertIn("session.automatic_message = action.instruction", self.source)
        self.assertIn("session.automatic_action_title = action.title", self.source)
        self.assertIn('presentation="action"', self.source)
        self.assertIn("display_text=title", self.source)
        self.assertIn("self._card_session(create=True)", self.source)
        self.assertIn("RequestKind.PRESET", self.source)

    def test_card_shortcuts_expose_only_opted_in_profile_actions(self) -> None:
        self.assertIn('"shortcuts": self._shortcut_payload()', self.source)
        self.assertIn("if action.show_on_card", self.source)
        self.assertIn(
            '"shortcuts_pending": self._card_shortcuts_pending()', self.source
        )

    def test_profile_save_refreshes_shortcuts_without_card_navigation(self) -> None:
        self.assertIn(
            "add_profile_change_listener(self._on_profiles_changed)", self.source
        )
        self.assertIn("def _on_profiles_changed", self.source)
        self.assertIn("self._render()", self.source)

    def test_preset_actions_render_a_safe_title_instead_of_the_instruction(
        self,
    ) -> None:
        self.assertIn('"text": (', self.source)
        self.assertIn("turn.display_text", self.source)
        self.assertIn("if turn.display_text is not None", self.source)
        self.assertIn("else turn.text", self.source)
        self.assertIn('"presentation": turn.presentation', self.source)
        self.assertIn("def _record_failed_action", self.source)

    def test_hide_and_workspace_close_are_distinct(self) -> None:
        self.assertIn("def minimize", self.source)
        self.assertIn("def close_workspace", self.source)
        self.assertIn("def restore_workspace", self.source)
        self.assertNotIn("get_store().discard(session.conversation_id)", self.source)
        self.assertIn("get_runtime().cancel(session.request_handle)", self.source)

    def test_workspace_payload_tracks_pending_work_and_runtime_scroll(self) -> None:
        self.assertIn('"workspace_has_sessions": bool(self._sessions)', self.source)
        self.assertIn(
            '"workspace_open": self._open and session is not None', self.source
        )
        self.assertIn('"workspace_pending": any(', self.source)
        self.assertIn(
            "self._is_busy(item) for item in self._sessions.values()", self.source
        )
        self.assertIn("def save_scroll", self.source)
        self.assertIn("scroll_following", self.source)

    def test_deck_general_has_no_card_context(self) -> None:
        self.assertIn('f"Deck: {name}"', self.source)
        self.assertIn('f"{name} · General"', self.source)

    def test_render_payload_exposes_quiet_connection_health(self) -> None:
        self.assertIn(
            '"connection_health": self._connection_health(session)', self.source
        )
        self.assertIn('return "connected"', self.source)
        self.assertIn('return "unavailable"', self.source)

    def test_bootstrap_builds_state_without_rendering_the_outgoing_webview(
        self,
    ) -> None:
        self.assertIn("def bootstrap(self, card)", self.source)
        self.assertIn("self._current_card, self._web = card, None", self.source)
        self.assertIn("return self._payload()", self.source)

    def test_pending_work_is_not_rendered_as_an_ambiguous_assistant_turn(self) -> None:
        self.assertNotIn("Waiting for another AI conversation", self.source)

    def test_pending_requests_and_preparing_actions_render_a_typing_turn(self) -> None:
        self.assertIn('session.request_state = "preparing"', self.source)
        self.assertIn(
            'turns.append({"role": "assistant", "typing": True})', self.source
        )
        self.assertIn(
            '"pending": bool(session and self._is_busy(session))', self.source
        )
        self.assertIn('"pending": self._is_busy(session)', self.source)

    def test_cancellation_and_failure_leave_the_composer_draft_untouched(self) -> None:
        self.assertIn(
            'self._render_for_session(key, status="Request cancelled.")', self.source
        )
        self.assertIn(
            'status=result.error_message or "Codex could not respond."', self.source
        )
        self.assertNotIn('composer=(message or "")', self.source)
