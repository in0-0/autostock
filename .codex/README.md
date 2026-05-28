# Codex Project Harness

This directory adapts the harness idea to Codex.

## What Codex Reads First

Codex should use the root [AGENTS.md](../AGENTS.md) as the primary project
instruction file.

## What Lives Here

- `skills/`: repository-local workflow playbooks.
- `roles/`: reviewer, developer, architect, and CLI tester role prompts for
  manual delegation or structured review passes.

These files are not Codex built-in commands. They are durable project checklists
that keep Codex work consistent across sessions.
