import json
from pathlib import Path
import unittest


class DefaultConfigTests(unittest.TestCase):
    def test_default_config_has_connection_and_deck_settings(self) -> None:
        path = Path(__file__).parents[1] / "src/anki_ai_workspace/config.json"
        config = json.loads(path.read_text(encoding="utf-8"))

        self.assertNotIn("codex_executable", config)
        self.assertEqual(config["codex_timeout_seconds"], 90)
        self.assertEqual(config["preset_reasoning_effort"], "low")
        self.assertEqual(config["custom_reasoning_effort"], "medium")
        self.assertEqual(config["model_verbosity"], "low")
