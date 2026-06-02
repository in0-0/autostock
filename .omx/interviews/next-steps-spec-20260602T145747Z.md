# Deep Interview: v0.2 Release Confidence Next Step

## Metadata

- Profile: standard
- Context type: brownfield
- Rounds: 4
- Final ambiguity: 12.8%
- Threshold: 20.0%
- Context snapshot: `.omx/context/next-steps-spec-20260602T145142Z.md`
- Status: crystallized / execution-ready for planning or safe local execution handoff


## Clarity Breakdown

| Dimension | Score | Remaining gap |
|---|---:|---|
| Intent | 0.92 | 목적은 v0.2 릴리스 확신으로 명확함 |
| Outcome | 0.90 | 필수 evidence bundle이 명확함 |
| Scope | 0.85 | Google Sheets/Telegram live smoke 제외가 명확함; scheduling/strategy는 암묵적 후순위 |
| Constraints | 0.85 | secret-safe local execution boundary가 명확함 |
| Success | 0.80 | smoke 결과와 release docs update 필요; 세부 명령/문서 위치는 planning에서 확정 가능 |
| Context | 0.90 | repo status/docs/tests preflight로 brownfield context 확보됨 |


## Intent

The next step should establish confidence that AutoStock v0.2 is release-ready, focused on the remaining live-provider validation evidence rather than expanding product scope.

## Desired Outcome

Produce a v0.2 release-confidence evidence bundle:

1. Bounded OpenDART live smoke evidence using locally available non-tracked credentials/environment, if available.
2. Bounded pykrx/FDR price-provider live smoke evidence for KOSPI/KOSDAQ universe/fallback/cache/telemetry behavior.
3. Release documentation update capturing the validation result and any remaining credential-dependent gaps.

## In-Scope

- OpenDART bounded live smoke.
- pykrx/FDR bounded live smoke.
- Capped/safe local execution when local configuration/environment is already available.
- Release confidence documentation updates.
- Clear recording of failures, exclusions, provider provenance, cache/freshness behavior, and residual risk.

## Out-of-Scope / Non-goals

- Real Google Sheets live smoke for this pass.
- Real Telegram live send for this pass.
- Any exposure of credential values in terminal output, docs, commits, logs, or reports.
- Credential creation, credential prompting, or asking the user to paste secret values.
- Direct product strategy changes unless planning discovers a blocker that invalidates release confidence.

## Decision Boundaries

OMX may proceed without another confirmation when all of the following hold:

- Execution is local and bounded.
- Any credential-dependent command uses already available local untracked settings or environment variables.
- Secret values are not printed, copied into docs, or committed.
- Network/API smoke is limited to the selected OpenDART and pykrx/FDR evidence paths.
- If credentials are missing or a provider is unavailable, OMX records the blocker/residual risk instead of requesting or exposing secrets.

OMX must not autonomously:

- Run Google Sheets live credential smoke.
- Send Telegram messages.
- Configure launchd/cron or alter production scheduling.
- Change scoring/strategy behavior as part of this interview handoff.

## Constraints

- Preserve repository credential safety rules.
- Keep generated runtime data under `data/` and avoid depending on generated outputs in tests.
- Use Korean for project docs under `docs/` if documentation updates are made.
- Run relevant tests or the smallest validation that proves the release-confidence claim.

## Testable Acceptance Criteria

- `python3 -m pytest` remains passing or any failure is documented as a blocker.
- OpenDART bounded live smoke is attempted only when a local key/env is available; result includes coverage/exclusion evidence or a credential/provider blocker.
- pykrx/FDR bounded live smoke is attempted in a capped configuration; result includes provider/fallback/cache/telemetry evidence or a provider/network blocker.
- Release docs record the evidence and clearly distinguish completed validation from deferred Google Sheets/Telegram live smoke.
- No tracked file contains API keys, Telegram token/chat IDs, Google credential JSON content, or account identifiers.

## Assumptions Exposed + Resolutions

- Assumption: v0.2 release confidence requires full end-to-end live credential smoke. Resolution: user selected OpenDART and pykrx/FDR live smoke plus release docs; Google Sheets live read and Telegram live send are explicitly out of scope for this pass.
- Assumption: OMX needs confirmation before any live provider call. Resolution: user selected Safe local execute; bounded OpenDART/pykrx/FDR execution is allowed when local non-tracked configuration is already available and secrets remain hidden.

## Pressure-Pass Findings

Round 3 revisited Round 2's omission of Google Sheets and Telegram live smoke. The user confirmed both are non-goals for this pass, and reinforced credential non-exposure as a hard constraint.

## Brownfield Evidence vs Inference Notes

- [from-code][auto-confirmed] `docs/STATUS.md` marks OpenDART/pykrx bounded live smoke as the remaining P0 item.
- [from-code][auto-confirmed] `docs/STATUS.md` lists real Google Sheets/Telegram credential smoke as P1, not P0.
- [from-code][auto-confirmed] `python3 -m pytest` passed with 61 tests during preflight.
- [from-code] v0.2 implementation appears largely complete from `docs/ROADMAP.md`; final release confidence still depends on selected live-provider smoke evidence.

## Technical Context Findings

- Current repo is a Python CLI batch MVP for Korean stock-market portfolio guidance.
- Runtime settings include `config/settings.yaml`, `config/settings.local.yaml`, and `config/settings.spreadsheet.example.yaml`; local credential files exist but must not be exposed or committed.
- Relevant commands from project instructions: `python3 -m src.main --settings config/settings.yaml` and `python3 -m pytest`.

## Recommended Handoff

Recommended next skill: `$ralplan` or `$ultragoal` using this spec as source of truth.

- `$ralplan`: best if the next step should first produce a concrete execution/test plan for the release-confidence smoke bundle.
- `$ultragoal`: best if the user wants durable sequential execution/checkpointing of the smoke bundle and docs update.
- `$autopilot`: acceptable if direct plan+execute+QA is desired using this clarified brief.
- `$team`: only if the work is split across parallel smoke, docs, and security-review lanes.
- `$ralph`: explicit fallback only for a narrow single-owner persistence loop.

## Transcript

### Round 4 — decision boundaries
- Question: 이번 v0.2 릴리스 확신 작업에서 OMX가 사용자 추가 확인 없이 자율적으로 해도 되는 결정/행동 범위는 어디까지인가요?
- Answer: ['Safe local execute']
- Ambiguity after: 0.1275

