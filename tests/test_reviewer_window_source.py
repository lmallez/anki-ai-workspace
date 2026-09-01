from pathlib import Path
import unittest

SOURCE_PATH = Path(__file__).parents[1] / "src" / "anki_ai_workspace" / "reviewer.py"


class ReviewerWindowSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_reviewer_loads_a_persistent_bridge_for_each_card_replacement(self) -> None:
        self.assertIn("gui_hooks.webview_will_set_content.append", self.source)
        self.assertIn("_inject_reviewer_bridge", self.source)
        self.assertIn("web/reviewer_bridge.js", self.source)

    def test_navigation_bootstraps_before_post_display_synchronization(self) -> None:
        self.assertIn("gui_hooks.reviewer_did_show_question.append", self.source)
        self.assertIn("def _on_reviewer_did_show_question", self.source)
        self.assertIn("controller.bootstrap(card)", self.source)
        self.assertIn('id="anki-ai-workspace-bootstrap"', self.source)
        self.assertNotIn(
            "controller.on_card_shown(card, getattr(mw.reviewer", self.source
        )

    def test_client_renders_bootstrap_before_requesting_sync(self) -> None:
        bootstrap_render = self.source.index("window.AnkiAIWorkspace.render(initial)")
        sync = self.source.index("send({action:'sync'})")
        self.assertLess(bootstrap_render, sync)

    def test_panel_can_be_hidden_without_removing_sessions(self) -> None:
        self.assertIn('id="anki-ai-workspace-minimize"', self.source)
        self.assertIn("action:'minimize'", self.source)
        self.assertIn('id="anki-ai-workspace-close"', self.source)
        self.assertIn("action:'close_workspace'", self.source)
        self.assertIn("'restore_workspace'", self.source)

    def test_selector_is_an_overlay_with_grouped_conversations(self) -> None:
        self.assertIn('id="anki-ai-workspace-selector"', self.source)
        self.assertIn("position:absolute;z-index:10", self.source)
        self.assertIn("group('Cards'", self.source)
        self.assertIn("group('Deck'", self.source)
        self.assertIn("anki-ai-workspace-session-pending", self.source)
        self.assertIn(
            "#anki-ai-workspace-selector button.anki-ai-workspace-session",
            self.source,
        )

    def test_document_transcript_and_integrated_composer_are_present(self) -> None:
        self.assertIn("#anki-ai-workspace-composer-shell", self.source)
        self.assertNotIn('id="anki-ai-workspace-plus"', self.source)
        self.assertIn('id="anki-ai-workspace-health"', self.source)
        self.assertIn('id="anki-ai-workspace-connection-popover"', self.source)
        self.assertIn("anki-ai-workspace-assistant{align-self:stretch", self.source)
        self.assertIn("sendButton.textContent=pending?'■':'↑'", self.source)

    def test_pending_requests_show_animated_typing_and_keep_the_composer_editable(
        self,
    ) -> None:
        self.assertIn("anki-ai-workspace-typing", self.source)
        self.assertIn("@keyframes anki-ai-workspace-typing", self.source)
        self.assertIn("turn.typing", self.source)
        self.assertIn("composer.disabled=!data.ready&&!pending", self.source)
        self.assertIn("sendButton.disabled=!data.ready&&!pending", self.source)
        self.assertIn("if(text&&!pending)", self.source)

    def test_preset_actions_have_a_distinct_user_style_without_exposing_instructions(
        self,
    ) -> None:
        self.assertIn("anki-ai-workspace-action", self.source)
        self.assertIn("anki-ai-workspace-action-kind", self.source)
        self.assertIn("kind.textContent='Action'", self.source)
        self.assertIn("title.textContent=turn.text", self.source)
        self.assertIn("actionState(turn.state)", self.source)

    def test_header_uses_traffic_lights_and_right_aligned_chevron(self) -> None:
        self.assertIn("#anki-ai-workspace-sessions::after", self.source)
        self.assertIn("#anki-ai-workspace-close{background:#ff5f57", self.source)
        self.assertIn("#anki-ai-workspace-minimize{background:#febc2e", self.source)
        self.assertNotIn("+'  ▾'", self.source)

    def test_launcher_opens_card_and_deck_contextual_actions(self) -> None:
        self.assertIn('id="anki-ai-workspace-launcher-new"', self.source)
        self.assertIn('id="anki-ai-workspace-launcher-restore"', self.source)
        self.assertIn("action:'open_custom'", self.source)
        self.assertIn("action:'open_deck_general'", self.source)
        self.assertIn("action:'select_action'", self.source)

    def test_opted_in_actions_render_as_direct_card_shortcuts(self) -> None:
        self.assertIn('id="anki-ai-workspace-shortcuts"', self.source)
        self.assertIn("data.shortcuts.forEach", self.source)
        self.assertIn("node.disabled=Boolean(data.shortcuts_pending)", self.source)
        self.assertIn("placeShortcuts", self.source)

    def test_shortcuts_use_one_compact_dark_toolbar(self) -> None:
        self.assertIn("background:rgba(17,17,17,.94)!important", self.source)
        self.assertIn("#anki-ai-workspace-shortcuts{position:fixed", self.source)
        self.assertIn("left:64px;bottom:20px", self.source)
        self.assertIn("height:34px", self.source)
        self.assertIn("height:28px", self.source)
        self.assertIn("color:#fff!important", self.source)
        self.assertIn("background:transparent!important", self.source)

    def test_profile_configuration_is_always_available_from_action_menu(self) -> None:
        empty_profile = self.source.index("if(!data.menu.has_profile)")
        configure = self.source.index("actions.append(button('Configure profiles…'")
        general = self.source.index(
            "actions.append(button(data.menu.deck_general_label"
        )
        divider = self.source.index("const managementDivider=document.createElement")
        self.assertLess(empty_profile, configure)
        self.assertLess(general, divider)
        self.assertLess(divider, configure)
        self.assertIn("anki-ai-workspace-management-divider", self.source)
        self.assertNotIn("anki-ai-workspace-configure::before", self.source)

    def test_reduced_launcher_uses_independent_new_and_restore_buttons(self) -> None:
        self.assertIn("anki-ai-workspace-has-hidden-workspace", self.source)
        self.assertIn("anki-ai-workspace-restore-dot", self.source)
        self.assertIn("action:'restore_workspace'", self.source)
        self.assertIn("action:'toggle_menu'", self.source)
        self.assertIn("workspace_has_sessions", self.source)
        self.assertIn("placeMenu", self.source)
        self.assertIn("action:'save_scroll'", self.source)
        self.assertIn("scroll_following", self.source)

    def test_launcher_remains_available_while_the_workspace_is_open(self) -> None:
        self.assertNotIn("launcher.hidden=Boolean(data.open)", self.source)
        self.assertIn("workspaceHidden=hasWorkspace&&!data.workspace_open", self.source)

    def test_resize_still_captures_pointer_and_clamps_to_viewport(self) -> None:
        self.assertIn("target.setPointerCapture(event.pointerId)", self.source)
        self.assertIn(
            "Math.min(Math.max(0,number(value.left,0)),width-nextWidth)", self.source
        )
        self.assertIn("addEventListener('resize'", self.source)
