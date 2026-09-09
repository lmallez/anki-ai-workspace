# Contributing

Thanks for helping with `anki-ai-workspace`.

This repository is intentionally small, so the best contributions are focused,
readable, and easy to review.

## Workflow

1. Create a branch from `main`.
2. Keep each pull request scoped to one topic.
3. Prefer small, reviewable changes over broad refactors.
4. Update tests and documentation when behavior changes.
5. Make sure local checks pass before opening a pull request.

## Local checks

Run these before asking for review:

```bash
make lint
make check
make test
```

Enable the repository's formatting check before committing:

```bash
make install-hooks
```

## Project rules

- Do not change Anki scheduling, intervals, note fields, or card content.
- Treat card and profile text as untrusted data at every UI and prompt boundary.
- Never write card text, profile text, prompts, replies, or credentials to logs.
- Keep the reviewer UI independent from the current Codex-specific backend.
- Keep portable profile definitions separate from local deck assignments.
- If add-on help text changes, update `src/anki_ai_workspace/README.md`.
- If GitHub-facing behavior changes, update `README.md` and `CHANGELOG.md`.

## Sensitive files

The following files are intentionally protected and should be edited carefully:

- `.github/workflows/*`
- `build.sh`
- `install.sh`
- `src/anki_ai_workspace/manifest.json`
- `src/anki_ai_workspace/config.json`
- `src/anki_ai_workspace/README.md`
- `CHANGELOG.md`

For these files:

- avoid unrelated drive-by edits
- explain clearly why the change is needed
- prefer a dedicated pull request for release or distribution changes

## Pull request guidance

A useful pull request description includes:

- what changed
- why it changed
- how it was tested
- whether documentation, configuration, or profiles changed

## Releases

Pushing a version tag runs formatting, compilation, and unit tests before
creating a GitHub Release with the `.ankiaddon` archive.

Publishing to AnkiWeb remains a separate manual step so the appropriate AnkiWeb
account can be used without storing personal publishing credentials in this
repository.

## Style

- Keep changes simple and explicit.
- Prefer stable, unsurprising architecture over clever abstractions.
- Preserve the safety boundary between Anki data, workspace UI, and AI requests.
