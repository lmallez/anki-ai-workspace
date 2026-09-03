from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from typing import Callable

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDesktopServices,
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
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    QUrl,
)

from .deck_profiles import DeckReference, deck_references
from .codex_client import (
    DEFAULT_CUSTOM_REASONING_EFFORT,
    DEFAULT_PRESET_REASONING_EFFORT,
    DEFAULT_TIMEOUT_SECONDS,
    CodexClient,
    normalize_model_verbosity,
    normalize_reasoning_effort,
)
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
from .ui.codex_runtime import get_runtime

USER_ROLE = Qt.ItemDataRole.UserRole
CODEX_CLI_GUIDE_URL = "https://learn.chatgpt.com/docs/codex/cli"
_dialog: "ProfileDialog | None" = None
_profile_change_listeners: list[Callable[[], None]] = []


def add_profile_change_listener(listener: Callable[[], None]) -> None:
    """Notify long-lived reviewer UI controllers after profile data is saved."""

    if listener not in _profile_change_listeners:
        _profile_change_listeners.append(listener)


def _notify_profile_change_listeners() -> None:
    for listener in tuple(_profile_change_listeners):
        listener()


def show_profile_dialog(tab: str = "profiles") -> None:
    global _dialog
    if _dialog is not None:
        _dialog.select_tab(tab)
        _dialog.show()
        _dialog.raise_()
        _dialog.activateWindow()
        return
    _dialog = ProfileDialog(mw, initial_tab=tab)
    _dialog.finished.connect(_dialog_closed)
    _dialog.show()


def show_codex_startup_prompt() -> None:
    """Explain the local Codex setup flow before opening the workspace."""

    prompt = CodexStartupDialog(mw)
    prompt.exec()
    if prompt.open_setup:
        show_profile_dialog("codex")


class CodexStartupDialog(QDialog):
    """A compact first-run setup card styled like the AI Workspace."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.open_setup = False
        self.setWindowTitle("Connect Codex")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(
            "QDialog { background: #ffffff; color: #111111; }"
            "#codex-setup-mark { background: #111111; border-radius: 22px; "
            "color: #ffffff; font-size: 22px; font-weight: 700; }"
            "#codex-setup-eyebrow { color: #737373; font-size: 11px; "
            "font-weight: 700; letter-spacing: 1.2px; }"
            "#codex-setup-title { font-size: 25px; font-weight: 700; }"
            "#codex-setup-copy { color: #5f5f5f; font-size: 14px; line-height: 1.45; }"
            "#codex-setup-steps { background: #f7f7f7; border: 1px solid #e8e8e8; "
            "border-radius: 14px; }"
            "#codex-setup-step-number { color: #888888; font-size: 11px; "
            "font-weight: 700; }"
            "#codex-setup-step-title { font-size: 14px; font-weight: 700; }"
            "#codex-setup-step-copy { color: #666666; font-size: 12px; }"
            "#codex-setup-primary { min-height: 42px; border: 0; border-radius: 10px; "
            "background: #111111; color: #ffffff; font-size: 14px; font-weight: 700; }"
            "#codex-setup-primary:hover { background: #2a2a2a; }"
            "#codex-setup-guide { min-height: 34px; border: 0; background: transparent; "
            "color: #444444; font-size: 13px; font-weight: 600; }"
            "#codex-setup-guide:hover { color: #111111; text-decoration: underline; }"
            "#codex-setup-later { border: 0; background: transparent; color: #888888; "
            "font-size: 12px; }"
            "#codex-setup-later:hover { color: #444444; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 22)
        root.setSpacing(16)

        mark = QLabel("✦")
        mark.setObjectName("codex-setup-mark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(44, 44)
        root.addWidget(mark)
        eyebrow = QLabel("AI WORKSPACE")
        eyebrow.setObjectName("codex-setup-eyebrow")
        root.addWidget(eyebrow)
        title = QLabel("Connect your local Codex")
        title.setObjectName("codex-setup-title")
        title.setWordWrap(True)
        root.addWidget(title)
        copy = QLabel(
            "AI Workspace uses the Codex CLI already installed on your computer. "
            "It never needs an API key."
        )
        copy.setObjectName("codex-setup-copy")
        copy.setWordWrap(True)
        root.addWidget(copy)

        steps = QFrame()
        steps.setObjectName("codex-setup-steps")
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(16, 10, 16, 10)
        steps_layout.setSpacing(8)
        for number, title_text, copy_text in (
            ("01", "Install Codex", "Follow the official Codex CLI guide."),
            ("02", "Sign in", "Run codex in a terminal and sign in with ChatGPT."),
            ("03", "Choose the executable", "Select and verify Codex in AI Workspace."),
        ):
            steps_layout.addWidget(_codex_setup_step(number, title_text, copy_text))
        root.addWidget(steps)

        setup_button = QPushButton("Set up Codex")
        setup_button.setObjectName("codex-setup-primary")
        setup_button.clicked.connect(self._open_setup)
        root.addWidget(setup_button)
        guide_button = QPushButton("Open Codex CLI guide ↗")
        guide_button.setObjectName("codex-setup-guide")
        guide_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CODEX_CLI_GUIDE_URL))
        )
        root.addWidget(guide_button)
        later_button = QPushButton("Not now")
        later_button.setObjectName("codex-setup-later")
        later_button.clicked.connect(self.reject)
        root.addWidget(later_button)

    def _open_setup(self) -> None:
        self.open_setup = True
        self.accept()


def _codex_setup_step(number: str, title: str, copy: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.setSpacing(12)
    number_label = QLabel(number)
    number_label.setObjectName("codex-setup-step-number")
    number_label.setFixedWidth(24)
    layout.addWidget(number_label, 0, Qt.AlignmentFlag.AlignTop)
    text = QWidget()
    text_layout = QVBoxLayout(text)
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(1)
    title_label = QLabel(title)
    title_label.setObjectName("codex-setup-step-title")
    text_layout.addWidget(title_label)
    copy_label = QLabel(copy)
    copy_label.setObjectName("codex-setup-step-copy")
    copy_label.setWordWrap(True)
    text_layout.addWidget(copy_label)
    layout.addWidget(text, 1)
    return row


def _dialog_closed(_result: int) -> None:
    global _dialog
    _dialog = None


def _codex_executable_filters() -> list[str]:
    if os.name == "nt":
        return [
            "Codex executable (codex.exe codex.cmd codex.bat)",
            "Executable files (*.exe *.cmd *.bat)",
            "All files (*)",
        ]
    return ["Codex executable (codex)", "All files (*)"]


def _setting_combo(
    options: tuple[tuple[str, str], ...], selected_value: str
) -> QComboBox:
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    combo.setCurrentIndex(max(0, combo.findData(selected_value)))
    return combo


def _reasoning_effort_options() -> tuple[tuple[str, str], ...]:
    return (
        ("Minimal", "minimal"),
        ("Low", "low"),
        ("Medium", "medium"),
        ("High", "high"),
        ("Extra high", "xhigh"),
    )


def _timeout_setting(value: object) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


class ProfileDialog(QDialog):
    def __init__(self, parent=None, *, initial_tab: str = "profiles") -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Workspace")
        data = get_profile_repository().load(refresh=True)
        self.profiles = [_profile_to_editable(profile) for profile in data.profiles]
        self.assignments = dict(data.assignments)
        self._loading = False
        self._dirty = False
        self._selected_profile = -1
        self._selected_action = -1
        self._file_dialog: QFileDialog | None = None
        self._codex_file_dialog: QFileDialog | None = None
        self._verified_executable: str | None = None
        self._saved_codex_executable = ""
        self._assignment_dialog: QDialog | None = None
        self._deck_rows: dict[str, tuple[QComboBox, QLabel, DeckReference]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.addTab(self._build_deck_profiles_page(), "Deck Profiles")
        self.workspace_tabs.addTab(self._build_codex_tab(), "Codex")
        root.addWidget(self.workspace_tabs, 1)

        self.import_button.clicked.connect(self._import_profile)
        self.export_button.clicked.connect(self._export_profile)
        self.assign_decks_button.clicked.connect(self._show_deck_assignments)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save)
        self._refresh_profile_list(select=0 if self.profiles else -1)
        self.select_tab(initial_tab)
        self._resize_to_available_screen()

    def select_tab(self, tab: str) -> None:
        self.workspace_tabs.setCurrentIndex(1 if tab == "codex" else 0)

    def _resize_to_available_screen(self) -> None:
        """Fit the dialog to the screen below its always-visible top toolbar."""

        available = self.screen().availableGeometry()
        width = min(1120, max(1, available.width() - 48))
        height = min(800, max(1, available.height() - 80))
        self.setMinimumSize(min(900, width), min(520, height))
        self.resize(width, height)

    def _build_deck_profiles_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.import_button = QPushButton("Import profile…")
        self.export_button = QPushButton("Export profile…")
        self.assign_decks_button = QPushButton("Deck assignments…")
        self.cancel_button = QPushButton("Cancel")
        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        for button in (
            self.import_button,
            self.export_button,
            self.assign_decks_button,
            self.cancel_button,
            self.save_button,
        ):
            button.setMinimumHeight(32)
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.assign_decks_button)
        toolbar.addStretch()
        toolbar.addWidget(self.cancel_button)
        toolbar.addWidget(self.save_button)
        layout.addLayout(toolbar)
        layout.addWidget(self._build_profiles_tab(), 1)
        return page

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
        self.action_list.setMaximumHeight(170)
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
        right_layout.addWidget(actions_group)
        right_layout.addStretch()
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
        self._refresh_assignment_options()
        return tab

    def _show_deck_assignments(self) -> None:
        if self._assignment_dialog is not None:
            self._assignment_dialog.raise_()
            self._assignment_dialog.activateWindow()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Deck assignments")
        dialog.setMinimumSize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(self._build_assignments_tab(), 1)
        footer = QHBoxLayout()
        note = QLabel("Changes are saved with Save in AI Workspace.")
        note.setStyleSheet("color: #737373;")
        footer.addWidget(note)
        footer.addStretch()
        close_button = QPushButton("Done")
        close_button.clicked.connect(dialog.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)
        self._assignment_dialog = dialog
        dialog.finished.connect(lambda _result: self._close_assignment_dialog())
        dialog.show()

    def _close_assignment_dialog(self) -> None:
        self._assignment_dialog = None

    def _build_codex_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 8, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        tab_layout.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        heading = QLabel("Codex")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(heading)
        header.addStretch()
        self.codex_help_button = QPushButton("?")
        self.codex_help_button.setFixedSize(28, 28)
        self.codex_help_button.setToolTip("How to set up Codex")
        header.addWidget(self.codex_help_button)
        layout.addLayout(header)

        connection_group = QGroupBox("Connection")
        connection_layout = QVBoxLayout(connection_group)
        connection_layout.setContentsMargins(16, 18, 16, 14)
        connection_layout.setSpacing(10)
        executable_row = QHBoxLayout()
        config = mw.addonManager.getConfig("anki_ai_workspace") or {}
        self._saved_codex_executable = str(config.get("codex_executable") or "").strip()
        self.codex_executable = QLineEdit(self._saved_codex_executable)
        self.codex_executable.setPlaceholderText("Choose a Codex executable…")
        self.browse_codex_button = QPushButton("Browse…")
        self.browse_codex_button.setMinimumHeight(32)
        executable_row.addWidget(self.codex_executable, 1)
        executable_row.addWidget(self.browse_codex_button)
        form = QFormLayout()
        self._configure_form(form)
        form.addRow("Codex executable", executable_row)
        connection_layout.addLayout(form)

        actions = QHBoxLayout()
        self.verify_codex_button = QPushButton("Verify")
        self.save_codex_button = QPushButton("Save settings")
        self.save_codex_button.setEnabled(bool(self._saved_codex_executable))
        for button in (self.verify_codex_button, self.save_codex_button):
            button.setMinimumHeight(32)
            actions.addWidget(button)
        actions.addStretch()
        connection_layout.addLayout(actions)
        self.codex_status = QLabel("Select an executable, then verify it.")
        self.codex_status.setWordWrap(True)
        connection_layout.addWidget(self.codex_status)
        layout.addWidget(connection_group)

        preferences_group = QGroupBox("How AI replies")
        preferences_layout = QFormLayout(preferences_group)
        preferences_layout.setContentsMargins(16, 18, 16, 14)
        self._configure_form(preferences_layout)

        self.model_verbosity = _setting_combo(
            (
                ("Concise", "low"),
                ("Normal", "medium"),
                ("Detailed", "high"),
            ),
            normalize_model_verbosity(config.get("model_verbosity")),
        )
        self.preset_reasoning_effort = _setting_combo(
            _reasoning_effort_options(),
            normalize_reasoning_effort(
                config.get("preset_reasoning_effort"),
                DEFAULT_PRESET_REASONING_EFFORT,
            ),
        )
        self.custom_reasoning_effort = _setting_combo(
            _reasoning_effort_options(),
            normalize_reasoning_effort(
                config.get("custom_reasoning_effort"),
                DEFAULT_CUSTOM_REASONING_EFFORT,
            ),
        )
        self.codex_timeout_seconds = QSpinBox()
        self.codex_timeout_seconds.setRange(1, 2_147_483_647)
        self.codex_timeout_seconds.setSuffix(" seconds")
        self.codex_timeout_seconds.setValue(
            _timeout_setting(config.get("codex_timeout_seconds"))
        )
        preferences_layout.addRow("Response detail", self.model_verbosity)
        preferences_layout.addRow(
            "Profile actions reasoning", self.preset_reasoning_effort
        )
        preferences_layout.addRow(
            "Custom questions reasoning", self.custom_reasoning_effort
        )
        preferences_layout.addRow("Reply timeout", self.codex_timeout_seconds)
        layout.addWidget(preferences_group)
        layout.addStretch()

        scroll.setWidget(content)

        self.browse_codex_button.clicked.connect(self._browse_codex)
        self.verify_codex_button.clicked.connect(self._verify_codex)
        self.save_codex_button.clicked.connect(self._save_codex)
        self.codex_help_button.clicked.connect(self._show_codex_setup_help)
        self.codex_executable.textChanged.connect(self._codex_executable_changed)
        return tab

    def _show_codex_setup_help(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Set up Codex")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText("Connect AI Workspace to your local Codex CLI")
        dialog.setInformativeText(
            "1. Install Codex using the official guide.\n\n"
            "2. Open a terminal, run codex, then choose Sign in with ChatGPT.\n\n"
            "3. Return here and choose the installed command. Select codex on "
            "macOS or Linux; on Windows, select codex.exe, codex.cmd, or codex.bat.\n\n"
            "AI Workspace does not scan for, download, or install Codex."
        )
        guide_button = dialog.addButton(
            "Open Codex CLI installation guide", QMessageBox.ButtonRole.ActionRole
        )
        dialog.addButton(QMessageBox.StandardButton.Close)
        dialog.exec()
        if dialog.clickedButton() is guide_button:
            QDesktopServices.openUrl(QUrl(CODEX_CLI_GUIDE_URL))

    def _browse_codex(self) -> None:
        dialog = QFileDialog(self, "Choose Codex executable")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilters(_codex_executable_filters())
        self._codex_file_dialog = dialog

        def finished(result: int) -> None:
            if result == int(QDialog.DialogCode.Accepted):
                selected = dialog.selectedFiles()
                if selected:
                    self.codex_executable.setText(selected[0])
            self._codex_file_dialog = None

        dialog.finished.connect(finished)
        dialog.open()

    def _codex_executable_changed(self, _text: str) -> None:
        self._verified_executable = None
        executable = self.codex_executable.text().strip()
        self.save_codex_button.setEnabled(executable == self._saved_codex_executable)
        self.codex_status.setText("Select an executable, then verify it.")

    def _verify_codex(self) -> bool:
        executable = self.codex_executable.text().strip()
        if not executable:
            self.codex_status.setText("Choose a Codex executable first.")
            return False
        result = CodexClient(executable).verify_executable()
        if not result.succeeded:
            self._verified_executable = None
            self.save_codex_button.setEnabled(False)
            self.codex_status.setText(
                result.error_message or "Codex could not be verified."
            )
            return False
        self._verified_executable = executable
        self.save_codex_button.setEnabled(True)
        self.codex_status.setText(result.text or "Codex executable verified.")
        return True

    def _save_codex(self) -> None:
        executable = self.codex_executable.text().strip()
        connection_changed = executable != self._saved_codex_executable
        if (
            connection_changed
            and executable != self._verified_executable
            and not self._verify_codex()
        ):
            return
        config = mw.addonManager.getConfig("anki_ai_workspace") or {}
        config["codex_executable"] = executable
        config["codex_timeout_seconds"] = self.codex_timeout_seconds.value()
        config["model_verbosity"] = self.model_verbosity.currentData()
        config["preset_reasoning_effort"] = self.preset_reasoning_effort.currentData()
        config["custom_reasoning_effort"] = self.custom_reasoning_effort.currentData()
        mw.addonManager.writeConfig("anki_ai_workspace", config)
        self._saved_codex_executable = executable
        self.save_codex_button.setEnabled(True)
        if connection_changed:
            get_runtime().reset_and_check_connection()
            self.codex_status.setText("Saved. Checking your Codex sign-in…")
            return
        self.codex_status.setText("Settings saved. New replies will use them.")

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
