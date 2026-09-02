# Hardened gauntlet loop — BreezeTTS build

Bar chosen (fixed by the goal doc, not re-litigated): for each **spec piece**
(stage output 01–06) the bar is that stage's own `## Audits` checklist in
`.icm/stages/NN-*/CONTEXT.md`, the exact facts in `.icm/references/*.md`
named by that stage's Inputs table, and the style rules in
`.icm/_config/voice.md` — named, fetchable (read those three sources),
comparable (a fresh reader checks every audit box and every quoted number
against the piece, blind to who wrote it). For each **code piece**
(schema_validator.py, engine module, handler.py, storage.py, Dockerfile,
requirements.txt) the bar is its own finished stage spec (02–05) plus
`python3 -m pytest tests/ -q` exit 0 for the tests that exercise it — same
fetch/compare mechanism.

## Loop prompt (paste-ready, operating procedure for this build)

Build the BreezeTTS RunPod worker spec-then-code, piece by piece. For each
piece the bar is that piece's own contract: the stage's `## Audits` box list,
the exact numbers/names in `.icm/references/*.md`, and `.icm/_config/voice.md`
style — for code pieces, add the finished stage spec and a green
`pytest tests/ -q`. Fetch the bar by reading those files directly, never from
memory or paraphrase. Build the piece. Then fan out a fresh-context critic
subagent that has not seen the builder's reasoning: hand it the piece with no
authorship label plus the bar files, and ask for a blind PASS/FAIL against
every audit box and every quoted fact, plus the single biggest remaining gap.
Praise is not useful — only the gap. Fix the gap, rebuild, send back to a
fresh critic call. Loop per piece until a critic call returns PASS with no
gap — never a fixed round count. Log every verdict (piece, round, gap or
PASS) to `.goals/progress.md` as a live page. When every piece is PASS, run
one final integration pass: `icm audit .icm --strict` plus the full pytest
suite, both green. Boundaries: stop after 20 tries total (per the goal doc);
no GPU/CUDA builds, no model downloads, no docker build/push, no network
calls from tested code paths, no credentials, no purchases, no deploys. On
exhausting the try budget on a piece, revert that piece's files and report.

## Self-audit against the 9 rules

| # | Rule | Verdict |
|---|---|---|
| 1 | Bar named/fetchable/comparable | PASS — bar is specific files (contract Audits, references/*.md, voice.md, plus tests/ for code), read directly each round |
| 2 | Critic is separate, fresh-context | PASS — critic is a fresh Task-agent call per round, given only the piece + bar files, not the builder's reasoning |
| 3 | Blind binary PASS/FAIL, no score | PASS — critic returns PASS/FAIL + single gap, no numeric score |
| 4 | Exit is winning or boundary, never round count | PASS — loop exits on critic PASS or the goal's 20-try boundary, not a fixed N |
| 5 | Boundaries present | PASS — inherited verbatim from the goal doc (try budget + forbidden actions) |
| 6 | Measurable half named where domain has one | PASS — pytest exit 0 named for code pieces |
| 7 | No dictated architecture beyond what the goal already fixed | PASS — module names/paths come from the goal/spec, not this prompt; internal structure is left to the builder |
| 8 | Live progress page instruction | PASS — `.goals/progress.md` updated every round |
| 9 | Final integration pass | PASS — `icm audit --strict` + full pytest as closing step |

All 9 pass. Proceeding to execute Phase 0.
