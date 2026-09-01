from __future__ import annotations

from pathlib import Path
import unittest

SOURCE_PATH = (
    Path(__file__).parents[1] / "src" / "anki_ai_workspace" / "profile_dialog.py"
)


class ProfileDialogSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_editor_opens_at_a_comfortable_size(self) -> None:
        self.assertIn("def _resize_to_available_screen", self.source)
        self.assertIn("available.height() - 80", self.source)

    def test_dialog_clamps_to_small_active_screens(self) -> None:
        self.assertIn("width = min(1120, max(1, available.width() - 48))", self.source)
        self.assertIn("height = min(800, max(1, available.height() - 80))", self.source)
        self.assertIn(
            "self.setMinimumSize(min(900, width), min(520, height))", self.source
        )
        self.assertNotIn("max(self.minimumWidth()", self.source)
        self.assertNotIn("max(self.minimumHeight()", self.source)

    def test_multiline_prompt_fields_have_room_for_real_prompts(self) -> None:
        self.assertIn("self.profile_context.setMinimumHeight(90)", self.source)
        self.assertIn("self.action_instruction.setMinimumHeight(120)", self.source)
        self.assertIn("self.action_instruction.setMaximumHeight(220)", self.source)

    def test_actions_can_be_exposed_as_review_card_shortcuts(self) -> None:
        self.assertIn("self.action_show_on_card = QCheckBox", self.source)
        self.assertIn("Show as a shortcut on review cards", self.source)
        self.assertIn('action["show_on_card"]', self.source)

    def test_button_rows_are_aligned_and_resist_overlap(self) -> None:
        self.assertIn("profile_buttons = QGridLayout()", self.source)
        self.assertIn("button.setMinimumHeight(32)", self.source)
        self.assertIn("button.setFixedSize(36, 32)", self.source)
        self.assertIn("splitter.setChildrenCollapsible(False)", self.source)

    def test_forms_wrap_cleanly_when_horizontal_space_is_tight(self) -> None:
        self.assertIn("def _configure_form", self.source)
        self.assertIn("QFormLayout.RowWrapPolicy.WrapLongRows", self.source)
        self.assertIn('QGroupBox("Profile details")', self.source)
        self.assertIn('QGroupBox("Actions")', self.source)

    def test_shortcut_row_has_reserved_space_below_instruction(self) -> None:
        self.assertIn("action_editor.setMinimumHeight(210)", self.source)
        self.assertIn("action_form = QGridLayout(action_editor)", self.source)
        self.assertIn("action_form.setRowMinimumHeight(2, 32)", self.source)
        self.assertIn("actions_group_layout.addWidget(action_editor)", self.source)

    def test_profile_editor_scrolls_when_vertical_space_is_limited(self) -> None:
        self.assertIn("right_scroll = QScrollArea()", self.source)
        self.assertIn("right_scroll.setWidgetResizable(True)", self.source)
        self.assertIn("Qt.ScrollBarPolicy.ScrollBarAsNeeded", self.source)
        self.assertIn("right_scroll.setWidget(right)", self.source)

    def test_primary_actions_remain_in_a_fixed_top_toolbar(self) -> None:
        toolbar = self.source.index("root.addLayout(toolbar, 0)")
        tabs = self.source.index("root.addWidget(self.tabs, 1)")
        resize = self.source.index("self._resize_to_available_screen()")
        self.assertLess(toolbar, tabs)
        self.assertLess(tabs, resize)
        self.assertIn("toolbar.addWidget(self.save_button)", self.source)

    def test_successful_save_notifies_reviewer_listeners(self) -> None:
        save = self.source.index("get_profile_repository().save")
        notify = self.source.index("_notify_profile_change_listeners()", save)
        accept = self.source.index("self.accept()", notify)
        self.assertLess(save, notify)
        self.assertLess(notify, accept)

    def test_cancelled_file_picker_keeps_profile_editor_open(self) -> None:
        self.assertIn("def _open_file_dialog", self.source)
        self.assertEqual(self.source.count("QFileDialog.Option.DontUseNativeDialog"), 2)
        self.assertIn("dialog.finished.connect(finished)", self.source)
        self.assertIn("dialog.open()", self.source)
        self.assertNotIn("dialog.exec()", self.source)
        self.assertNotIn("QFileDialog.getOpenFileName", self.source)
        self.assertNotIn("QFileDialog.getSaveFileName", self.source)

    def test_export_completion_does_not_accept_the_profile_dialog(self) -> None:
        export = self.source.index("def _export_profile")
        picker = self.source.index("def _open_file_dialog", export)
        section = self.source[export:picker]
        self.assertIn("self._open_file_dialog(", section)
        self.assertNotIn("self.accept()", section)
