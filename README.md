# Anki AI Workspace

[![CI](https://github.com/lmallez/anki-ai-workspace/actions/workflows/ci.yml/badge.svg)](https://github.com/lmallez/anki-ai-workspace/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

> Warning
> Anki AI Workspace is beta software and may contain bugs or change without
> notice.
> AI requests can consume usage allowances or credits and may incur costs under
> your provider plan. Monitor your usage and keep Anki backups.
> Use it at your own risk. I am not responsible for credit consumption,
> unexpected costs, data loss, deck or profile issues, or other side effects.

![AI Workspace helping with the card currently being reviewed](docs/images/anki-ai-workspace.png)

> AI chat in Anki, tailored to your decks. Powered by your locally authenticated Codex CLI.

Ask about the card you are reviewing without leaving Anki. The current card is
included automatically as context, actions tell the AI what to do with it, and
profiles give different decks their own actions. No API key is required.

## Features

- 💬 Chat with AI using the current card as automatic context
- 🧩 Create reusable actions for explanations, mnemonics, exercises, and more
- 🗂️ Give each deck its own set of actions
- 🔒 Keep conversations temporary and your cards untouched

## Custom actions and profiles

An **action** is a reusable instruction you define once and use while reviewing.
For example: **Explain simply**, **Create a mnemonic**, or **Make a practice
exercise**. Select one and AI Workspace runs it with the current card as context.

A **profile** is a set of actions for a deck. Give each deck the tools it needs;
subdecks inherit their parent profile by default.

## Requirements

- Anki with add-on support
- The Codex CLI installed and signed in

The packaged add-on supports Windows, macOS, and Linux. After installing Codex,
use **Tools → AI Workspace… → Codex** to select its executable, or type
`codex` when it is available in Anki's PATH.

## Install

1. Download `anki_ai_workspace.ankiaddon` from this project's release assets.
2. In Anki, choose **File → Import** and select the downloaded file.
3. Restart Anki when prompted.

## Set up Codex

On first startup, AI Workspace shows a setup popup because no Codex executable
is configured yet. Follow the [official Codex CLI guide](https://learn.chatgpt.com/docs/codex/cli),
install Codex, run `codex` in a terminal, and sign in with your ChatGPT account.
Then select and verify the executable in **Tools → AI Workspace… → Codex**.
That tab keeps the complete setup guide, connection controls, and reply
preferences together.

Install Codex using its official documentation, then run:

```bash
codex
```

After completing sign-in, start Anki and select the installed Codex executable
in **Tools → AI Workspace… → Codex**. The same page lets you choose response
detail, reasoning effort for profile actions and custom questions, and the
reply timeout. These are AI Workspace preferences; Codex account, updates, and
global CLI configuration stay in Codex.

## Usage

1. Review any card and select the sparkle button.
2. Choose a profile action, or choose **Custom chat** to type a question.
3. Open **Tools → AI Workspace…** to create profiles, assign them to
   decks.

Profile exports contain only profile definitions. Deck assignments stay local
to the Anki installation.

## Privacy

Requests run through your locally authenticated Codex CLI in a temporary,
read-only working directory. Conversations remain in memory only for the active
Anki session.

AI Workspace does not modify card content, note fields, scheduling, or
intervals. Operational logs exclude card text, profile text, prompts, replies,
credentials, and raw Codex output.

## Troubleshooting

- **Codex CLI was not found:** confirm that `codex --version` works in a new
  terminal, then restart Anki.
- **Codex is not signed in:** run `codex` in a terminal and complete sign-in.
- **A request is taking too long:** cancel it in the workspace and try again.

## Development

Requires Python 3.13.

```bash
git clone https://github.com/lmallez/anki-ai-workspace.git
cd anki-ai-workspace
make install-dev
make install-hooks
make lint
make check
make test
make build VERSION=0.1.0
```

Use `make install VERSION=0.1.0` to install a source build locally. The archive
is written to `dist/anki_ai_workspace.ankiaddon`. See the
[configuration reference](src/anki_ai_workspace/config.md) for advanced options.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for project
rules, local checks, and pull request guidance.

## License

Anki AI Workspace is available under the [MIT License](LICENSE).
