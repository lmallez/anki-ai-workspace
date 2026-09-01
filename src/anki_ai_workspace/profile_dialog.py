from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
)

from .deck_profiles import DeckReference, deck_references
from .profiles import (
    DeckProfile,
    ProfileAction,
    ProfileValidationError,
    get_profile_repository,
    new_id,
    read_profile_file,
    validate_profiles,
    write_profile_file,
)

USER_ROLE = Qt.ItemDataRole.UserRole
_dialog: "ProfileDialog | None" = None
_profile_change_listeners: list[Callable[[], None]] = []


def add_profile_change_listener(listener: Callable[[], None]) -> None:
    """Notify long-lived reviewer UI controllers after profile data is saved."""

    if listener not in _profile_change_listeners:
        _profile_change_listeners.append(listener)


def _notify_profile_change_listeners() -> None:
    for listener in tuple(_profile_change_listeners):
        listener()


def show_profile_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.show()
        _dialog.raise_()
        _dialog.activateWindow()
        return
    _dialog = ProfileDialog(mw)
    _dialog.finished.connect(_dialog_closed)
    _dialog.show()


def _dialog_closed(_result: int) -> None:
    global _dialog
    _dialog = None


class ProfileDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Deck Profiles")
        data = get_profile_repository().load(refresh=True)
        self.profiles = [_profile_to_editable(profile) for profile in data.profiles]
        self.assignments = dict(data.assignments)
        self._loading = False
        self._dirty = False
        self._selected_profile = -1
        self._selected_action = -1
        self._file_dialog: QFileDialog | None = None
        self._deck_rows: dict[str, tuple[QComboBox, QLabel, DeckReference]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.import_button = QPushButton("Import profile…")
        self.export_button = QPushButton("Export profile…")
        self.cancel_button = QPushButton("Cancel")
        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        for button in (
            self.import_button,
            self.export_button,
            self.cancel_button,
            self.save_button,
        ):
            button.setMinimumHeight(32)
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.export_button)
        toolbar.addStretch()
        toolbar.addWidget(self.cancel_button)
        toolbar.addWidget(self.save_button)
        root.addLayout(toolbar, 0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_profiles_tab(), "Profiles")
        self.tabs.addTab(self._build_assignments_tab(), "Deck Assignment")
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)

        self.import_button.clicked.connect(self._import_profile)
        self.export_button.clicked.connect(self._export_profile)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save)
        self._refresh_profile_list(select=0 if self.profiles else -1)
        self._refresh_assignment_options()
        self._resize_to_available_screen()

    def _resize_to_available_screen(self) -> None:
        """Fit the dialog to the screen below its always-visible top toolbar."""

        available = self.screen().availableGeometry()
        width = min(1120, max(1, available.width() - 48))
        height = min(800, max(1, available.height() - 80))
        self.setMinimumSize(min(900, width), min(520, height))
        self.resize(width, height)

    def _build_profiles_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        layout.addWidget(splitter)

        left = QWidget()
        left.setMinimumWidth(160)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        profile_heading = QLabel("Profiles")
        profile_heading.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(profile_heading)
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._profile_selected)
        left_layout.addWidget(self.profile_list)
        profile_buttons = QGridLayout()
        profile_buttons.setHorizontalSpacing(6)
        profile_buttons.setVerticalSpacing(6)
        self.new_profile_button = QPushButton("New")
        self.duplicate_profile_button = QPushButton("Duplicate")
        self.delete_profile_button = QPushButton("Delete")
        for column, button in enumerate(
            (
                self.new_profile_button,
                self.duplicate_profile_button,
                self.delete_profile_button,
            )
        ):
            button.setMinimumHeight(32)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            profile_buttons.addWidget(button, 0, column)
            profile_buttons.setColumnStretch(column, 1)
        left_layout.addLayout(profile_buttons)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 8, 8)
        right_layout.setSpacing(12)

        profile_group = QGroupBox("Profile details")
        profile_group_layout = QVBoxLayout(profile_group)
        profile_group_layout.setContentsMargins(12, 14, 12, 12)
        form = QFormLayout()
        self._configure_form(form)
        self.profile_name = QLineEdit()
        self.profile_title_field = QLineEdit()
        self.profile_title_field.setPlaceholderText(
            "Exact note field name (blank = first readable field)"
        )
        self.profile_context = QTextEdit()
        self.profile_context.setPlaceholderText(
            "Example: I am a B1 language learner. Keep explanations concise."
        )
        self.profile_context.setMinimumHeight(90)
        self.profile_context.setMaximumHeight(140)
        form.addRow("Name", self.profile_name)
        form.addRow("Title field", self.profile_title_field)
        form.addRow("Context", self.profile_context)
        profile_group_layout.addLayout(form)
        right_layout.addWidget(profile_group)

        actions_group = QGroupBox("Actions")
        actions_group_layout = QVBoxLayout(actions_group)
        actions_group_layout.setContentsMargins(12, 14, 12, 12)
        actions_group_layout.setSpacing(8)
        self.action_list = QListWidget()
        self.action_list.setMinimumHeight(120)
        self.action_list.currentRowChanged.connect(self._action_selected)
        actions_group_layout.addWidget(self.action_list, 1)
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(6)
        self.add_action_button = QPushButton("Add action")
        self.delete_action_button = QPushButton("Delete")
        self.action_up_button = QPushButton("↑")
        self.action_down_button = QPushButton("↓")
        self.add_action_button.setMinimumWidth(110)
        self.delete_action_button.setMinimumWidth(90)
        for button in (self.add_action_button, self.delete_action_button):
            button.setMinimumHeight(32)
            action_buttons.addWidget(button)
        action_buttons.addStretch()
        for button, tooltip in (
            (self.action_up_button, "Move action up"),
            (self.action_down_button, "Move action down"),
        ):
            button.setFixedSize(36, 32)
            button.setToolTip(tooltip)
            action_buttons.addWidget(button)
        actions_group_layout.addLayout(action_buttons)
        action_editor = QWidget()
        action_editor.setMinimumHeight(210)
        action_form = QGridLayout(action_editor)
        action_form.setContentsMargins(0, 0, 0, 0)
        action_form.setHorizontalSpacing(12)
        action_form.setVerticalSpacing(8)
        action_form.setColumnMinimumWidth(0, 92)
        action_form.setColumnStretch(1, 1)
        self.action_title = QLineEdit()
        self.action_instruction = QTextEdit()
        self.action_instruction.setPlaceholderText(
            "The instruction automatically sent when this action is selected."
        )
        self.action_instruction.setMinimumHeight(120)
        self.action_instruction.setMaximumHeight(220)
        self.action_instruction.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        self.action_show_on_card = QCheckBox("Show as a shortcut on review cards")
        self.action_show_on_card.setMinimumHeight(32)
        action_labels = (
            QLabel("Button title"),
            QLabel("Instruction"),
            QLabel("Shortcut"),
        )
        for label in action_labels:
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        action_form.addWidget(action_labels[0], 0, 0)
        action_form.addWidget(self.action_title, 0, 1)
        action_form.addWidget(action_labels[1], 1, 0)
        action_form.addWidget(self.action_instruction, 1, 1)
        action_form.addWidget(action_labels[2], 2, 0)
        action_form.addWidget(self.action_show_on_card, 2, 1)
        action_form.setRowMinimumHeight(2, 32)
        action_form.setRowStretch(1, 1)
        actions_group_layout.addWidget(action_editor)
        right_layout.addWidget(actions_group, 1)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 790])

        self.new_profile_button.clicked.connect(self._new_profile)
        self.duplicate_profile_button.clicked.connect(self._duplicate_profile)
        self.delete_profile_button.clicked.connect(self._delete_profile)
        self.add_action_button.clicked.connect(self._add_action)
        self.delete_action_button.clicked.connect(self._delete_action)
        self.action_up_button.clicked.connect(lambda: self._move_action(-1))
        self.action_down_button.clicked.connect(lambda: self._move_action(1))
        self.profile_name.textChanged.connect(self._edited)
        self.profile_title_field.textChanged.connect(self._edited)
        self.profile_context.textChanged.connect(self._edited)
        self.action_title.textChanged.connect(self._edited)
        self.action_instruction.textChanged.connect(self._edited)
        self.action_show_on_card.toggled.connect(self._edited)
        return tab

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        """Keep labels and fields readable when fonts or window size increase."""

        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

    def _build_assignments_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        explanation = QLabel(
            "Assign a profile directly, or inherit the nearest parent deck's profile. "
            "Deck renames keep their assignment."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.deck_tree = QTreeWidget()
        self.deck_tree.setHeaderLabels(
            ["Deck", "Assigned profile", "Effective profile"]
        )
        self.deck_tree.setColumnWidth(0, 300)
        self.deck_tree.setColumnWidth(1, 230)
        layout.addWidget(self.deck_tree)
        self._populate_decks()
        return tab

    def _populate_decks(self) -> None:
        self.deck_tree.clear()
        self._deck_rows.clear()
        items_by_name: dict[str, QTreeWidgetItem] = {}
        for reference in deck_references():
            parent_name = reference.name.rpartition("::")[0]
            parent = items_by_name.get(parent_name)
            item = QTreeWidgetItem(parent if parent is not None else self.deck_tree)
            item.setText(0, reference.name.rsplit("::", 1)[-1])
            item.setData(0, USER_ROLE, str(reference.id))
            combo = QComboBox()
            effective = QLabel()
            self.deck_tree.setItemWidget(item, 1, combo)
            self.deck_tree.setItemWidget(item, 2, effective)
            combo.currentIndexChanged.connect(self._assignment_changed)
            self._deck_rows[str(reference.id)] = (combo, effective, reference)
            items_by_name[reference.name] = item
        self.deck_tree.expandAll()

    def _profile_selected(self, row: int) -> None:
        if self._loading:
            return
        self._store_current_fields()
        self._selected_profile = row
        self._selected_action = -1
        self._load_profile_fields()

    def _action_selected(self, row: int) -> None:
        if self._loading:
            return
        self._store_action_fields()
        self._selected_action = row
        self._load_action_fields()

    def _load_profile_fields(self) -> None:
        self._loading = True
        valid = 0 <= self._selected_profile < len(self.profiles)
        profile = self.profiles[self._selected_profile] if valid else None
        self.profile_name.setText(profile["name"] if profile else "")
        self.profile_title_field.setText(profile["title_field"] if profile else "")
        self.profile_context.setPlainText(profile["context"] if profile else "")
        self.profile_name.setEnabled(valid)
        self.profile_title_field.setEnabled(valid)
        self.profile_context.setEnabled(valid)
        self.action_list.clear()
        if profile:
            self.action_list.addItems(action["title"] for action in profile["actions"])
        self._loading = False
        self.action_list.setCurrentRow(0 if profile and profile["actions"] else -1)
        self._set_profile_controls(valid)

    def _load_action_fields(self) -> None:
        self._loading = True
        action = self._current_action()
        self.action_title.setText(action["title"] if action else "")
        self.action_instruction.setPlainText(action["instruction"] if action else "")
        self.action_show_on_card.setChecked(
            bool(action["show_on_card"]) if action else False
        )
        self.action_title.setEnabled(action is not None)
        self.action_instruction.setEnabled(action is not None)
        self.action_show_on_card.setEnabled(action is not None)
        self.delete_action_button.setEnabled(action is not None)
        self.action_up_button.setEnabled(
            action is not None and self._selected_action > 0
        )
        actions = self._current_actions()
        self.action_down_button.setEnabled(
            action is not None and self._selected_action < len(actions) - 1
        )
        self._loading = False

    def _store_current_fields(self) -> None:
        if not (0 <= self._selected_profile < len(self.profiles)):
            return
        self._store_action_fields()
        profile = self.profiles[self._selected_profile]
        profile["name"] = self.profile_name.text().strip()
        profile["title_field"] = self.profile_title_field.text().strip()
        profile["context"] = self.profile_context.toPlainText().strip()
        item = self.profile_list.item(self._selected_profile)
        if item is not None:
            item.setText(profile["name"] or "Untitled profile")

    def _store_action_fields(self) -> None:
        action = self._current_action()
        if action is None:
            return
        action["title"] = self.action_title.text().strip()
        action["instruction"] = self.action_instruction.toPlainText().strip()
        action["show_on_card"] = self.action_show_on_card.isChecked()
        item = self.action_list.item(self._selected_action)
        if item is not None:
            item.setText(action["title"] or "Untitled action")

    def _new_profile(self) -> None:
        self._store_current_fields()
        self.profiles.append(
            {
                "id": new_id(),
                "name": "",
                "title_field": "",
                "context": "",
                "actions": [],
            }
        )
        self._dirty = True
        self._refresh_profile_list(select=len(self.profiles) - 1)
        self.profile_name.setFocus()

    def _duplicate_profile(self) -> None:
        self._store_current_fields()
        if not (0 <= self._selected_profile < len(self.profiles)):
            return
        source = deepcopy(self.profiles[self._selected_profile])
        source["id"] = new_id()
        source["name"] = (source["name"] or "Untitled profile") + " copy"
        for action in source["actions"]:
            action["id"] = new_id()
        self.profiles.append(source)
        self._dirty = True
        self._refresh_profile_list(select=len(self.profiles) - 1)

    def _delete_profile(self) -> None:
        if not (0 <= self._selected_profile < len(self.profiles)):
            return
        name = self.profiles[self._selected_profile]["name"] or "Untitled profile"
        answer = QMessageBox.question(
            self,
            "Delete profile",
            f"Delete “{name}”? Decks assigned to it will become unassigned.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        profile_id = self.profiles[self._selected_profile]["id"]
        del self.profiles[self._selected_profile]
        self.assignments = {
            deck_id: assigned
            for deck_id, assigned in self.assignments.items()
            if assigned != profile_id
        }
        self._dirty = True
        self._refresh_profile_list(
            select=min(self._selected_profile, len(self.profiles) - 1)
        )

    def _add_action(self) -> None:
        if not (0 <= self._selected_profile < len(self.profiles)):
            return
        self._store_current_fields()
        actions = self._current_actions()
        actions.append(
            {
                "id": new_id(),
                "title": "",
                "instruction": "",
                "show_on_card": False,
            }
        )
        self._dirty = True
        self._refresh_action_list(select=len(actions) - 1)
        self.action_title.setFocus()

    def _delete_action(self) -> None:
        actions = self._current_actions()
        if not (0 <= self._selected_action < len(actions)):
            return
        del actions[self._selected_action]
        self._dirty = True
        self._refresh_action_list(select=min(self._selected_action, len(actions) - 1))

    def _move_action(self, offset: int) -> None:
        self._store_action_fields()
        actions = self._current_actions()
        destination = self._selected_action + offset
        if not (
            0 <= self._selected_action < len(actions)
            and 0 <= destination < len(actions)
        ):
            return
        actions[self._selected_action], actions[destination] = (
            actions[destination],
            actions[self._selected_action],
        )
        self._dirty = True
        self._refresh_action_list(select=destination)

    def _refresh_profile_list(self, *, select: int) -> None:
        self._loading = True
        self.profile_list.clear()
        self.profile_list.addItems(
            profile["name"] or "Untitled profile" for profile in self.profiles
        )
        self._selected_profile = -1
        self._loading = False
        self.profile_list.setCurrentRow(select)
        if select < 0:
            self._load_profile_fields()

    def _refresh_action_list(self, *, select: int) -> None:
        self._loading = True
        self.action_list.clear()
        self.action_list.addItems(
            action["title"] or "Untitled action" for action in self._current_actions()
        )
        self._selected_action = -1
        self._loading = False
        self.action_list.setCurrentRow(select)
        if select < 0:
            self._load_action_fields()

    def _set_profile_controls(self, valid: bool) -> None:
        self.duplicate_profile_button.setEnabled(valid)
        self.delete_profile_button.setEnabled(valid)
        self.add_action_button.setEnabled(valid)
        self.export_button.setEnabled(valid)
        if not valid:
            self._load_action_fields()

    def _current_actions(self) -> list[dict[str, str]]:
        if not (0 <= self._selected_profile < len(self.profiles)):
            return []
        return self.profiles[self._selected_profile]["actions"]

    def _current_action(self) -> dict[str, str] | None:
        actions = self._current_actions()
        if not (0 <= self._selected_action < len(actions)):
            return None
        return actions[self._selected_action]

    def _edited(self) -> None:
        if not self._loading:
            self._dirty = True

    def _tab_changed(self, _index: int) -> None:
        self._store_current_fields()
        self._refresh_assignment_options()

    def _refresh_assignment_options(self) -> None:
        self._loading = True
        profile_ids = {profile["id"] for profile in self.profiles}
        for deck_id, (combo, _effective, _reference) in self._deck_rows.items():
            selected = self.assignments.get(deck_id)
            combo.clear()
            combo.addItem("Inherit from parent", None)
            for profile in self.profiles:
                combo.addItem(profile["name"] or "Untitled profile", profile["id"])
            index = combo.findData(selected) if selected in profile_ids else 0
            combo.setCurrentIndex(max(0, index))
        self._loading = False
        self._update_effective_labels()

    def _assignment_changed(self) -> None:
        if self._loading:
            return
        for deck_id, (combo, _effective, _reference) in self._deck_rows.items():
            profile_id = combo.currentData()
            if profile_id:
                self.assignments[deck_id] = str(profile_id)
            else:
                self.assignments.pop(deck_id, None)
        self._dirty = True
        self._update_effective_labels()

    def _update_effective_labels(self) -> None:
        profiles = {profile["id"]: profile["name"] for profile in self.profiles}
        ids_by_name = {
            reference.name: str(reference.id)
            for _combo, _label, reference in self._deck_rows.values()
        }
        for deck_id, (_combo, label, reference) in self._deck_rows.items():
            candidate_ids = [deck_id]
            parts = reference.name.split("::")
            for length in range(len(parts) - 1, 0, -1):
                parent_id = ids_by_name.get("::".join(parts[:length]))
                if parent_id:
                    candidate_ids.append(parent_id)
            assigned = next(
                (
                    self.assignments[candidate]
                    for candidate in candidate_ids
                    if self.assignments.get(candidate) in profiles
                ),
                None,
            )
            direct = self.assignments.get(deck_id)
            if assigned is None:
                label.setText("None")
            elif direct == assigned:
                label.setText(profiles[assigned])
            else:
                label.setText("Inherited: " + profiles[assigned])

    def _editable_profiles(self) -> tuple[DeckProfile, ...]:
        self._store_current_fields()
        return tuple(_profile_from_editable(profile) for profile in self.profiles)

    def _save(self) -> None:
        try:
            profiles = validate_profiles(self._editable_profiles())
            get_profile_repository().save(profiles, self.assignments)
        except ProfileValidationError as error:
            QMessageBox.warning(self, "Cannot save profiles", str(error))
            return
        self._dirty = False
        _notify_profile_change_listeners()
        self.accept()

    def _import_profile(self) -> None:
        dialog = QFileDialog(self, "Import AI Workspace profile")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("JSON files (*.json)")
        self._open_file_dialog(dialog, self._import_profile_file)

    def _import_profile_file(self, filename: str) -> None:
        try:
            profile = read_profile_file(filename)
        except ProfileValidationError as error:
            QMessageBox.warning(self, "Cannot import profile", str(error))
            return
        used_profile_ids = {value["id"] for value in self.profiles}
        used_action_ids = {
            action["id"] for value in self.profiles for action in value["actions"]
        }
        editable = _profile_to_editable(profile)
        if editable["id"] in used_profile_ids:
            editable["id"] = new_id()
        for action in editable["actions"]:
            if action["id"] in used_action_ids:
                action["id"] = new_id()
        self.profiles.append(editable)
        self._dirty = True
        self._refresh_profile_list(select=len(self.profiles) - 1)

    def _export_profile(self) -> None:
        if not (0 <= self._selected_profile < len(self.profiles)):
            return
        try:
            profile = validate_profiles(
                (self._editable_profiles()[self._selected_profile],)
            )[0]
        except ProfileValidationError as error:
            QMessageBox.warning(self, "Cannot export profile", str(error))
            return
        default_name = "-".join(profile.name.lower().split()) or "ai-workspace-profile"
        dialog = QFileDialog(self, "Export AI Workspace profile")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilter("JSON files (*.json)")
        dialog.setDefaultSuffix("json")
        dialog.selectFile(str(Path.home() / f"{default_name}.json"))
        self._open_file_dialog(
            dialog, lambda filename: write_profile_file(profile, filename)
        )

    def _open_file_dialog(
        self, dialog: QFileDialog, on_selected: Callable[[str], None]
    ) -> None:
        """Open a child picker without nesting an event loop in this dialog."""

        if self._file_dialog is not None:
            self._file_dialog.raise_()
            self._file_dialog.activateWindow()
            return
        self._file_dialog = dialog

        def finished(result: int) -> None:
            filenames = (
                dialog.selectedFiles() if result == QDialog.DialogCode.Accepted else []
            )
            if self._file_dialog is dialog:
                self._file_dialog = None
            dialog.deleteLater()
            if filenames:
                on_selected(filenames[0])

        dialog.finished.connect(finished)
        dialog.open()

    def reject(self) -> None:
        if self._dirty:
            answer = QMessageBox.question(
                self,
                "Discard changes?",
                "Discard the unsaved profile and deck-assignment changes?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().reject()


def _profile_to_editable(profile: DeckProfile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "title_field": profile.title_field,
        "context": profile.context,
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


def _profile_from_editable(value: dict) -> DeckProfile:
    return DeckProfile(
        str(value["id"]),
        str(value["name"]).strip(),
        str(value["context"]).strip(),
        tuple(
            ProfileAction(
                str(action["id"]),
                str(action["title"]).strip(),
                str(action["instruction"]).strip(),
                bool(action.get("show_on_card", False)),
            )
            for action in value["actions"]
        ),
        str(value.get("title_field", "")).strip(),
    )
