from pathlib import Path
import unittest

SOURCE_PATH = Path(__file__).parents[1] / "src" / "anki_ai_workspace" / "addon.py"


class AddonSourceTests(unittest.TestCase):
    def test_tools_menu_has_one_unified_workspace_entry(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn('addAction("AI Workspace…")', source)
        self.assertNotIn("AI Deck Profiles…", source)

    def test_missing_codex_configuration_prompts_after_initial_deck_browser(
        self,
    ) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("gui_hooks.state_did_change.append", source)
        self.assertIn('if new_state != "deckBrowser"', source)
        self.assertIn("gui_hooks.state_did_change.remove", source)
        self.assertIn(
            "QTimer.singleShot(0, _show_codex_startup_prompt_if_needed)", source
        )
        self.assertIn('config.get("codex_setup_prompt_dismissed")', source)
        self.assertNotIn("QTimer.singleShot(0, show_codex_startup_prompt)", source)
        self.assertIn("def _configured_codex_executable()", source)
