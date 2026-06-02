# Deep Interview Context Snapshot: next-steps-spec

- Created UTC: 20260602T145142Z
- Task statement: Conduct a deep interview to decide the next work and specification decisions from AutoStock's current state.
- Desired outcome: An execution-ready next-step spec that can feed planning/execution without reopening broad requirements discovery.
- Stated solution: Use `$deep-interview` before deciding implementation/planning route.
- Probable intent hypothesis: The owner wants to avoid misaligned next-phase work after v0.2.0 implementation coverage appears mostly complete, and to choose between live smoke validation, release hardening, and v0.3.0 operationalization.

## Known facts / evidence

- `docs/STATUS.md` says current status is v0.2.0 service spec implementation verification, last updated 2026-06-01.
- `docs/ROADMAP.md` marks v0.2.0 goals and release gates as implemented/passed, but `docs/STATUS.md` still lists live credential/network smoke checks as open.
- `docs/STATUS.md` P0 open item: OpenDART/pykrx bounded live smoke with local API key/network.
- `docs/STATUS.md` P1 open item: real Google Sheets and Telegram credential smoke.
- `docs/STATUS.md` P2 open item: clearer separation between sample/fixture settings and personal operational settings.
- `docs/ROADMAP.md` v0.3.0 scope: weekend schedule template, config separation, Telegram retry/failure policy, runbook/rollback/checklist, provider rate-limit/stale-cache/partial-failure logging.
- Git working tree was clean before interview preflight.
- `python3 -m pytest` passed: 61 passed, 15 warnings on 2026-06-02 KST.

## Constraints

- Do not commit secrets, API tokens, chat IDs, account numbers, or credential files.
- Project docs under `docs/` should be Korean unless explicitly requested otherwise.
- Deep interview is requirements-only; do not implement directly in this mode.
- Any real credential/live smoke path may need local untracked settings and should not expose secret values.

## Unknowns / open questions

- Which next-step outcome matters most now: v0.2.0 release confidence, v0.3.0 operational hardening, strategy quality, or configuration/security cleanup?
- Which live smoke checks are allowed/available locally, and what evidence counts as enough?
- What must remain explicitly out of scope for the next pass?
- What decisions may OMX make autonomously versus requiring owner confirmation?
- Whether next handoff should be `$ralplan`, `$ultragoal`, `$autopilot`, `$team`, or further interview.

## Decision-boundary unknowns

- Whether to run live network/provider checks with local credentials.
- Whether schedule/launchd setup is allowed or only documented.
- Whether Telegram live send is allowed or should be simulated/disabled.
- Whether config separation is code work, docs work, or both.

## Likely codebase touchpoints

- `config/settings*.yaml`
- `src/collectors/`, `src/engines/`, `src/utils/`, `src/main.py`
- `docs/STATUS.md`, `docs/ROADMAP.md`, `docs/guides/`, `docs/architecture/`
- `tests/test_phase1.py`

## Prompt-safe initial-context summary status

- not_needed
