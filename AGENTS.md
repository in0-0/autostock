# AGENTS.md

AutoStock instructions for Codex. Keep this file short; project memory lives in
`docs/`, and optional Codex workflow notes live in `codex/`.

> **Project:** [README.md](./README.md) |
> **Status:** [STATUS.md](./docs/STATUS.md) |
> **Roadmap:** [ROADMAP.md](./docs/ROADMAP.md) |
> **History:** [HISTORY.md](./docs/HISTORY.md)

## Project Shape

AutoStock is a weekend batch MVP for Korean stock market portfolio guidance.
It is currently a Python CLI pipeline with mock broker data, local JSON outputs,
and Telegram Markdown report rendering.

Core directories:
- `src/collectors/`: broker and market data collection
- `src/engines/`: macro, fundamental, technical, exit, portfolio logic
- `src/brokers/`: broker connector interfaces and implementations
- `src/utils/`: config, Telegram, and atomic write helpers
- `tests/`: regression tests for Phase 1 behavior
- `config/settings.yaml`: runtime settings; treat secrets with care
- `data/`: generated runtime outputs

## Development Commands

```bash
python3 -m src.main --settings config/settings.yaml
python3 -m pytest
```

Optional dependency setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Codex Workflow

Start new work by reading:
- `docs/STATUS.md` for the current state
- `docs/ROADMAP.md` for planned work
- `docs/HISTORY.md` for past releases
- relevant domain docs under `docs/architecture/`, `docs/api/`, and `docs/guides/`

For larger work, use the project workflow notes under `.codex/skills/`:

```text
issue -> plan -> implement -> qa -> pr -> review -> release -> deploy
```

These are repository-local playbooks, not automatic slash commands. Use them as
checklists while working in Codex.

## Documentation and Git Rules

- Write agent-facing notes and internal workflow documents under `.omx/` in English.
- Write project documentation under `docs/` in Korean so the project owner can review it easily, unless the user explicitly asks for another language.
- After every completed modification, including documentation-only changes, stage and commit the files changed for that task. Do not include unrelated user changes in the commit.

## Engineering Rules

- Run `python3 -m pytest` after code changes.
- Preserve existing module boundaries and Pydantic model style.
- Use `atomic_write_json` for persistent JSON outputs.
- Keep generated files under `data/`; do not depend on generated output in tests.
- Prefer deterministic sample data until real broker and market providers are added.
- Do not commit API tokens, chat IDs, account numbers, or credential files.
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
