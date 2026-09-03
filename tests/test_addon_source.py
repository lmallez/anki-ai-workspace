from pathlib import Path
import unittest

SOURCE_PATH = Path(__file__).parents[1] / "src" / "anki_ai_workspace" / "addon.py"


class AddonSourceTests(unittest.TestCase):
    def test_tools_menu_has_one_unified_workspace_entry(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn('addAction("AI Workspace…")', source)
        self.assertNotIn("AI Deck Profiles…", source)

    def test_missing_codex_configuration_prompts_during_startup(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("if not _configured_codex_executable()", source)
        self.assertIn("QTimer.singleShot(0, show_codex_startup_prompt)", source)
        self.assertIn("def _configured_codex_executable()", source)
