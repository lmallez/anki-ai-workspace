from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from anki_ai_workspace.codex_client import CodexErrorKind, CodexResult


def _runtime_module():
    module_name = "anki_ai_workspace.ui.codex_runtime"
    sys.modules.pop(module_name, None)
    aqt = ModuleType("aqt")
    aqt.mw = SimpleNamespace()
    with patch.dict(sys.modules, {"aqt": aqt}):
        return importlib.import_module(module_name)


class CodexRuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        sys.modules.pop("anki_ai_workspace.ui.codex_runtime", None)

    def test_reset_notifies_persistent_listeners_and_ignores_stale_results(
        self,
    ) -> None:
        runtime_module = _runtime_module()
        runtime = runtime_module.AnkiCodexRuntime()
        started = []
        statuses = []
        runtime._start_request = started.append
        runtime._client = lambda: SimpleNamespace(check_connection=lambda: None)
        runtime.add_status_listener(statuses.append)
        completion_statuses = []

        runtime.reset_and_check_connection(completion_statuses.append)
        first = started[-1]
        runtime.reset_and_check_connection()

        self.assertEqual(statuses[-1].state, runtime_module.ConnectionState.CHECKING)
        first.on_finished(first.handle, CodexResult(text="old connection"))
        self.assertEqual(statuses[-1].state, runtime_module.ConnectionState.CHECKING)

        second = started[-1]
        second.on_finished(
            second.handle,
            CodexResult(
                error_kind=CodexErrorKind.EXECUTABLE_BROKEN,
                error_message="Not Codex",
            ),
        )

        self.assertEqual(statuses[-1].state, runtime_module.ConnectionState.NEEDS_SETUP)
        self.assertEqual(statuses[-1].result.error_message, "Not Codex")
        self.assertEqual(
            completion_statuses[-1].state, runtime_module.ConnectionState.NEEDS_SETUP
        )
