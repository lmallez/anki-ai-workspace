# Changelog

## 0.2.0 - 2026-09-09

- Added guided Codex setup, connection verification, and reply preferences.
- Improved connection recovery, diagnostics, and cross-platform Codex support.
- Added `./install.sh --clean <version>` to reset add-on settings safely.
- Added optional profile-action shortcuts that run directly from review cards.
- Refined card shortcuts into a compact toolbar while keeping profile management
  available from the action menu.
- Reworked the profile editor with responsive, scrollable layout and controls
  that remain accessible on smaller or scaled displays.
- Refresh reviewer actions and shortcut buttons immediately after profile data
  is saved, without requiring card navigation or an Anki restart.
- Preserved profiles and local deck assignments across upgrades by including
  `user_files` in release archives.

## 0.1.0 - 2026-08-31

- Added the initial Anki AI Workspace add-on, deck profiles, reviewer workspace,
  Codex CLI integration, packaging, and release automation.
- Added contributor guidance, code ownership, and the same opt-in pre-commit
  formatting hook used by Anki Slot Machine.
