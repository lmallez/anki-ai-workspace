# Anki AI Workspace configuration

The reviewer AI button is shown for every card in every deck. Configure
its deck-specific actions from **Tools → AI Deck Profiles…**.

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

`codex_executable` is the Codex CLI command or full path. It defaults to
`codex`, so the add-on uses the version available on the user's PATH. The
add-on uses the account signed in through that CLI and does not use an API
key.

`codex_timeout_seconds` is the maximum time to wait for each AI reply.
The default is 90 seconds.

The add-on automatically uses `preset_reasoning_effort` (`low`) for profile
actions and `custom_reasoning_effort` (`medium`) for typed questions.
`model_verbosity` defaults to `low`. Invalid values fall back to these safe
defaults; these advanced options do not appear in the profile editor.

Preset actions send no earlier chat history. Typed questions receive only the
latest three complete exchanges, while the inline window may continue showing
up to twenty exchanges. Card context is capped at 12,000 characters and each
historical turn at 4,000 characters to prevent unexpectedly large prompts.

Codex is started only after you send a message. The add-on allows one request
at a time, so Anki remains responsive; use Cancel in the
chat window to stop a pending reply.

The first-use connection check verifies the executable and sends a small test
request through saved Codex CLI authentication. If the CLI needs repair, run
`npm install -g @openai/codex@latest`; if it needs authentication, run
`codex --login` and complete its sign-in flow.

If the check fails, Chat shows a Retry connection button and a copyable safe
diagnostic. The diagnostic includes only the stage, status, executable, version,
and exit code—never card or chat text.

Operational startup logs are written to Anki's log folder as
`anki_ai_workspace.log`. The file records task submission, Codex process start,
completion, timeout, failure category, request kind, reasoning setting, and
character counts for prompt sections and responses. It never records card text,
profile text, chat messages, credentials, prompts, or Codex output. It rotates
automatically.
