# Anki AI Workspace configuration

The reviewer AI button is shown for every card in every deck. Configure
deck-specific actions and the Codex connection from **Tools → AI Workspace…**.

Profiles are stored in `user_files/profiles.json`. Local deck-ID assignments
are stored separately in `user_files/deck_assignments.json`, so exported
profiles never contain deck information. Both files are preserved when the
add-on is upgraded.

A deck inherits the nearest profile assigned to one of its parents. Renaming a
deck keeps its direct assignment because assignments use Anki's internal deck
IDs. Selecting a profile action sends its instruction automatically; Custom
chat opens an empty composer while retaining the profile's answer context.
Actions marked **Show as a shortcut on review cards** also appear as direct
buttons beside the sparkle launcher. These buttons use the same inherited
profile and action execution path as the action menu.

`codex_executable` is initially unset. On startup, the add-on explains how to
install and sign in to Codex, then lets you select a command or full path in
the **Codex** tab. The add-on uses the account signed in through that CLI and
does not use an API key.

The **Codex** tab is the complete setup page. It links to the official Codex
CLI installation guide, explains how to sign in by running `codex` in a
terminal, and lets you browse to an already-installed executable, verify it
with `--version`, and save it. It does not scan for, install, or download
Codex. On Windows, select `codex.exe`, `codex.cmd`, or `codex.bat`; on macOS
and Linux, select `codex`.

For setup, open the [official Codex CLI guide](https://learn.chatgpt.com/docs/codex/cli),
install Codex, then run `codex` in a terminal and sign in before selecting its
executable in Anki.

The **How AI replies** card in the Codex tab manages the add-on's local reply
preferences. `codex_timeout_seconds` is the maximum time to wait for each AI
reply; it defaults to 90 seconds and has a one-second minimum. `model_verbosity`
controls response detail: concise (`low`), normal (`medium`), or detailed
(`high`).

The add-on uses `preset_reasoning_effort` for profile actions and
`custom_reasoning_effort` for typed questions. Both can be set in the Codex
tab from minimal through extra high; defaults are `low` and `medium`.
Invalid values fall back to these safe defaults. Codex account, updates, and
global CLI configuration remain managed by Codex itself.

Preset actions send no earlier chat history. Typed questions receive only the
latest three complete exchanges, while the inline window may continue showing
up to twenty exchanges. Card context is capped at 12,000 characters and each
historical turn at 4,000 characters to prevent unexpectedly large prompts.

Codex is started only after you send a message. The add-on allows one request
at a time, so Anki remains responsive; use Cancel in the
chat window to stop a pending reply.

The first-use connection check verifies the executable and sends a small test
request through saved Codex CLI authentication. If the CLI needs repair, use
the official Codex CLI guide. If it needs authentication, run `codex` in a
terminal and complete its sign-in flow.

If the check fails, Chat shows a Retry connection button and a copyable safe
diagnostic. The diagnostic includes only the stage, status, executable, version,
and exit code—never card or chat text.

Operational startup logs are written to Anki's log folder as
`anki_ai_workspace.log`. The file records task submission, Codex process start,
completion, timeout, failure category, request kind, reasoning setting, and
character counts for prompt sections and responses. It never records card text,
profile text, chat messages, credentials, prompts, or Codex output. It rotates
automatically.
