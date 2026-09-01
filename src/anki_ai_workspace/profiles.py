from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Iterable, Mapping
from uuid import uuid4

SCHEMA_VERSION = 1
PROFILES_FILENAME = "profiles.json"
ASSIGNMENTS_FILENAME = "deck_assignments.json"


class ProfileValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileAction:
    id: str
    title: str
    instruction: str
    show_on_card: bool = False


@dataclass(frozen=True)
class DeckProfile:
    id: str
    name: str
    context: str
    actions: tuple[ProfileAction, ...]
    # Empty means "first readable field", which keeps older exported profiles valid.
    title_field: str = ""


@dataclass(frozen=True)
class ProfileData:
    profiles: tuple[DeckProfile, ...]
    assignments: dict[str, str]


def new_id() -> str:
    return uuid4().hex


def validate_profiles(profiles: Iterable[DeckProfile]) -> tuple[DeckProfile, ...]:
    normalized = tuple(profiles)
    profile_ids: set[str] = set()
    action_ids: set[str] = set()
    for profile in normalized:
        if not profile.id.strip() or profile.id in profile_ids:
            raise ProfileValidationError("Every profile must have a unique ID.")
        if not profile.name.strip():
            raise ProfileValidationError("Every profile must have a name.")
        profile_ids.add(profile.id)
        for action in profile.actions:
            if not action.id.strip() or action.id in action_ids:
                raise ProfileValidationError("Every action must have a unique ID.")
            if not action.title.strip():
                raise ProfileValidationError("Every action must have a title.")
            if not action.instruction.strip():
                raise ProfileValidationError("Every action must have an instruction.")
            action_ids.add(action.id)
    return normalized


class ProfileRepository:
    """Portable profiles and machine-local deck assignments."""

    def __init__(self, user_files_directory: str | Path) -> None:
        self.directory = Path(user_files_directory)
        self._data: ProfileData | None = None

    def load(self, *, refresh: bool = False) -> ProfileData:
        if self._data is not None and not refresh:
            return self._data
        profiles = self._read_profiles()
        assignments = self._read_assignments()
        valid_ids = {profile.id for profile in profiles}
        assignments = {
            str(deck_id): profile_id
            for deck_id, profile_id in assignments.items()
            if profile_id in valid_ids
        }
        self._data = ProfileData(profiles, assignments)
        return self._data

    def save(
        self,
        profiles: Iterable[DeckProfile],
        assignments: Mapping[str | int, str],
    ) -> ProfileData:
        normalized_profiles = validate_profiles(profiles)
        valid_ids = {profile.id for profile in normalized_profiles}
        normalized_assignments = {
            str(deck_id): str(profile_id)
            for deck_id, profile_id in assignments.items()
            if str(profile_id) in valid_ids
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        _write_json(
            self.directory / PROFILES_FILENAME,
            {
                "schema_version": SCHEMA_VERSION,
                "profiles": [
                    _profile_to_dict(profile) for profile in normalized_profiles
                ],
            },
        )
        _write_json(
            self.directory / ASSIGNMENTS_FILENAME,
            {
                "schema_version": SCHEMA_VERSION,
                "assignments": normalized_assignments,
            },
        )
        self._data = ProfileData(normalized_profiles, normalized_assignments)
        return self._data

    def export_profile(self, profile_id: str, destination: str | Path) -> None:
        profile = profile_by_id(self.load(), profile_id)
        if profile is None:
            raise ProfileValidationError("The selected profile no longer exists.")
        write_profile_file(profile, destination)

    def import_profile(self, source: str | Path) -> DeckProfile:
        imported = read_profile_file(source)
        current = self.load()
        used_profile_ids = {profile.id for profile in current.profiles}
        used_action_ids = {
            action.id for profile in current.profiles for action in profile.actions
        }
        profile_id = imported.id if imported.id not in used_profile_ids else new_id()
        actions = tuple(
            ProfileAction(
                action.id if action.id not in used_action_ids else new_id(),
                action.title,
                action.instruction,
                action.show_on_card,
            )
            for action in imported.actions
        )
        imported = DeckProfile(
            profile_id,
            imported.name,
            imported.context,
            actions,
            imported.title_field,
        )
        self.save((*current.profiles, imported), current.assignments)
        return imported

    def _read_profiles(self) -> tuple[DeckProfile, ...]:
        raw = _read_json(self.directory / PROFILES_FILENAME, {})
        values = raw.get("profiles", []) if isinstance(raw, dict) else []
        if not isinstance(values, list):
            return ()
        try:
            return validate_profiles(_profile_from_dict(value) for value in values)
        except (KeyError, TypeError, ProfileValidationError):
            return ()

    def _read_assignments(self) -> dict[str, str]:
        raw = _read_json(self.directory / ASSIGNMENTS_FILENAME, {})
        values = raw.get("assignments", {}) if isinstance(raw, dict) else {}
        if not isinstance(values, dict):
            return {}
        return {
            str(deck_id): str(profile_id)
            for deck_id, profile_id in values.items()
            if isinstance(profile_id, str)
        }


def profile_by_id(data: ProfileData, profile_id: str | None) -> DeckProfile | None:
    if not profile_id:
        return None
    return next(
        (profile for profile in data.profiles if profile.id == profile_id), None
    )


def read_profile_file(source: str | Path) -> DeckProfile:
    raw = _read_json(Path(source), {})
    if not isinstance(raw, dict) or not isinstance(raw.get("profile"), dict):
        raise ProfileValidationError("This is not an AI Workspace profile file.")
    profile = _profile_from_dict(raw["profile"])
    return validate_profiles((profile,))[0]


def write_profile_file(profile: DeckProfile, destination: str | Path) -> None:
    validate_profiles((profile,))
    _write_json(
        Path(destination),
        {"schema_version": SCHEMA_VERSION, "profile": _profile_to_dict(profile)},
    )


def resolve_profile(
    data: ProfileData,
    deck_id: int | str,
    deck_name: str,
    deck_ids_by_name: Mapping[str, int | str],
) -> DeckProfile | None:
    """Resolve a direct assignment, then the closest assigned parent deck."""

    candidate_ids = [str(deck_id)]
    parts = str(deck_name).split("::")
    for length in range(len(parts) - 1, 0, -1):
        parent_id = deck_ids_by_name.get("::".join(parts[:length]))
        if parent_id is not None:
            candidate_ids.append(str(parent_id))
    for candidate_id in candidate_ids:
        profile = profile_by_id(data, data.assignments.get(candidate_id))
        if profile is not None:
            return profile
    return None


def _profile_from_dict(raw: object) -> DeckProfile:
    if not isinstance(raw, dict):
        raise ProfileValidationError("Invalid profile data.")
    actions_raw = raw.get("actions", [])
    if not isinstance(actions_raw, list):
        raise ProfileValidationError("Invalid action data.")
    return DeckProfile(
        str(raw["id"]),
        str(raw["name"]).strip(),
        str(raw.get("context", "")).strip(),
        tuple(
            ProfileAction(
                str(action["id"]),
                str(action["title"]).strip(),
                str(action["instruction"]).strip(),
                action.get("show_on_card") is True,
            )
            for action in actions_raw
            if isinstance(action, dict)
        ),
        str(raw.get("title_field", "")).strip(),
    )


def _profile_to_dict(profile: DeckProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "context": profile.context,
        "title_field": profile.title_field,
        "actions": [
            {
                "id": action.id,
                "title": action.title,
                "instruction": action.instruction,
                "show_on_card": action.show_on_card,
            }
            for action in profile.actions
        ],
    }


def _read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(value, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


_repository = ProfileRepository(Path(__file__).resolve().parent / "user_files")


def get_profile_repository() -> ProfileRepository:
    return _repository
