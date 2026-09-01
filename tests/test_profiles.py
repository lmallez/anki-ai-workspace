from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from anki_ai_workspace.profiles import (
    DeckProfile,
    ProfileAction,
    ProfileRepository,
    ProfileValidationError,
    read_profile_file,
    resolve_profile,
    write_profile_file,
)


def profile(profile_id: str, name: str = "Language") -> DeckProfile:
    return DeckProfile(
        profile_id,
        name,
        "I am a B1 learner.",
        (ProfileAction(f"{profile_id}-action", "Explain", "Explain this card."),),
    )


class ProfileRepositoryTests(unittest.TestCase):
    def test_empty_install_loads_without_creating_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = ProfileRepository(directory)

            data = repository.load()

            self.assertEqual(data.profiles, ())
            self.assertEqual(data.assignments, {})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_save_round_trip_uses_separate_portable_and_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = ProfileRepository(directory)
            repository.save((profile("kr"),), {123: "kr"})
            reloaded = ProfileRepository(directory).load()

            self.assertEqual(reloaded.profiles[0].name, "Language")
            self.assertEqual(reloaded.assignments, {"123": "kr"})
            portable = json.loads(
                (Path(directory) / "profiles.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("assignments", portable)

    def test_title_field_round_trips_and_legacy_profiles_default_to_blank(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = ProfileRepository(directory)
            repository.save(
                (
                    DeckProfile(
                        "language", "Language", "", (), title_field="Expression"
                    ),
                ),
                {},
            )
            self.assertEqual(
                ProfileRepository(directory).load().profiles[0].title_field,
                "Expression",
            )
            legacy = Path(directory) / "legacy.json"
            legacy.write_text(
                '{"schema_version": 1, "profile": {"id": "legacy", "name": "Legacy", "context": "", "actions": []}}',
                encoding="utf-8",
            )
            self.assertEqual(read_profile_file(legacy).title_field, "")

    def test_card_shortcut_round_trips_and_legacy_actions_default_to_hidden(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = ProfileRepository(directory)
            shortcut = DeckProfile(
                "kr",
                "Korean",
                "",
                (ProfileAction("explain", "Explain", "Explain it.", True),),
            )
            repository.save((shortcut,), {})
            self.assertTrue(
                ProfileRepository(directory).load().profiles[0].actions[0].show_on_card
            )

            legacy = Path(directory) / "legacy-action.json"
            legacy.write_text(
                '{"schema_version": 1, "profile": {"id": "legacy", "name": "Legacy", "context": "", "actions": [{"id": "explain", "title": "Explain", "instruction": "Explain it."}]}}',
                encoding="utf-8",
            )
            self.assertFalse(read_profile_file(legacy).actions[0].show_on_card)

    def test_nearest_parent_assignment_and_direct_override(self) -> None:
        data = ProfileRepositoryTests._data(
            (profile("parent"), profile("child", "Grammar")),
            {"1": "parent", "3": "child"},
        )
        ids = {
            "Languages": 1,
            "Languages::Vocabulary": 2,
            "Languages::Vocabulary::Grammar": 3,
        }

        inherited = resolve_profile(data, 2, "Languages::Vocabulary", ids)
        overridden = resolve_profile(data, 3, "Languages::Vocabulary::Grammar", ids)

        self.assertEqual(inherited.id, "parent")
        self.assertEqual(overridden.id, "child")

    def test_deleted_profile_assignments_are_ignored(self) -> None:
        data = ProfileRepositoryTests._data((profile("kept"),), {"1": "deleted"})
        self.assertIsNone(resolve_profile(data, 1, "Languages", {"Languages": 1}))

    def test_export_excludes_deck_assignments_and_import_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            write_profile_file(profile("kr"), path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            imported = read_profile_file(path)

            self.assertEqual(imported.id, "kr")
            self.assertNotIn("assignments", raw)

    def test_validation_rejects_empty_action_instruction(self) -> None:
        broken = DeckProfile(
            "broken",
            "Broken",
            "",
            (ProfileAction("action", "Explain", ""),),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProfileValidationError):
                ProfileRepository(directory).save((broken,), {})

    @staticmethod
    def _data(profiles, assignments):
        from anki_ai_workspace.profiles import ProfileData

        return ProfileData(tuple(profiles), dict(assignments))
