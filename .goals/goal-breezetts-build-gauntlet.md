# Goal: Build BreezeTTS from the ICM workspace, under gauntlet discipline

Created 2026-09-01 by /goal-creator. Human-check policy: proceed + flag
(agent-verified — pending human). Scope decision: spec layer completed by the
pipeline walk, then the entire project is implemented from it.

---

/goal Build out the entire BreezeTTS RunPod serverless project from the ICM
workspace at .icm/ — first finish and correct the spec, then implement the
worker from it — under gauntlet discipline (invoke the gauntlet skill in
GENERATE mode first to harden this loop: real bar, builder + separate
fresh-context critic per piece, blind comparison, loop until the critic picks
ours — never a round count; live progress page; one final integration pass).

PHASE 0 — spec check: Read .icm/IDENTITY.md → .icm/CONTEXT.md → every stage
contract under .icm/stages/*/CONTEXT.md. `icm audit .icm --strict` (icm skill
scripts: /root/.claude/skills/icm/scripts/{run,audit,sync}) must exit 0. Verify
every Audits checkbox in stages 01–05 is pinned by the workspace; if the spec
is incomplete or internally inconsistent, correct it (stage output/ docs and
references/ are the edit surface; contracts only for genuine errors), run
`icm sync` after any structural change, and log every correction in
.goals/spec-corrections.md.

PHASE 1 — pipeline traversal: walk stages 01→06 in order. Per stage: load only
the files its Inputs table names, produce its Outputs at the contract-named
paths, and perform the human check yourself — header each output
`Human check: agent-verified — pending human`. Stage 06's check is binding:
every audit box in stages 02–05 must map to a named test in
output/verification-and-test-suite.md.

PHASE 2 — build: implement in the repo root per the finished specs:
schema_validator.py, the engine-lifecycle module, handler.py, storage.py,
Dockerfile, requirements.txt (explicit pins, botocore>=1.36 floor).
Pieces: one per stage output (01–06), then one per code module. For each
piece the bar is its stage contract's Audits list + the facts in
.icm/references/ + the spec style in .icm/_config/voice.md; fan out a builder
and a separate critic subagent with fresh context — the critic inspects the
actual output, compares blind (labels stripped) against the bar, names the
single biggest remaining gap, loops until it picks ours. Confirm runpod SDK
and boto3/botocore API usage against Context7 docs before coding them.
Record each piece's blind verdict in .goals/progress.md. Once source files
exist, run `codegraph sync` and keep it fresh — navigate code with it, not
grep/Read sweeps.

Done when ALL hold (evaluator checks each):
1. `icm audit .icm --strict` exits 0, 0 violations, 0 warnings.
2. All six stage outputs exist at contract-named paths:
   stages/01…/output/discovery-and-contracts.md, 02…/schema-and-validation.md,
   03…/engine-and-model-lifecycle.md, 04…/handler-and-storage.md,
   05…/container-and-dockerfile.md, 06…/verification-and-test-suite.md —
   and stage 01's pinned facts appear in them verbatim: 24 kHz mono 16-bit
   PCM WAV; eager ~7.7 GiB / `--fast-all` ~14.4 GiB; 4 MB per clip / 6 MB
   total decoded; `RUNPOD_INIT_TIMEOUT=1200`; `ENTRYPOINT []`.
3. Stage 06's plan covers: golden-payload tests for all 3 modes; all 8 vocal
   cues (4 EN + 4 ZH) as passthrough; mocked S3 upload+presign asserting the
   B2 checksum config, key template, and all 7 response fields; base64
   fallback when credentials absent; 4 MB / 6 MB boundary tests (accept at
   bound, reject one over); `python3 handler.py --test_input '<json>'` per
   mode; container smoke check against the stage 05 spec.
4. Repo root contains working schema_validator.py, engine module, handler.py,
   storage.py, Dockerfile, requirements.txt.
5. `python3 -m pytest tests/ -q` exits 0 — every test CPU-only, network-free
   (mocked S3 client, no model download).
6. Dockerfile contains literal `ENTRYPOINT []`, `RUNPOD_INIT_TIMEOUT=1200`,
   and an unbuffered CMD (`python3 -u`).
7. Every stage 02–05 audit box maps to a test in the suite.
8. No hardcoded credentials: `grep -rEin 'access_key|secret_key|app_key'`
   across source shows only os.environ / Secret-container lookups.
9. .goals/progress.md shows a blind-critic verdict for every piece, and every
   stage output is headed `Human check: agent-verified — pending human`.

Scope: .icm/** (write stage outputs + needed corrections), repo-root source,
tests, Dockerfile, requirements.txt. Don't touch: stage contracts
(.icm/stages/*/CONTEXT.md) except genuine spec errors (log them),
.outline/, AGENTS.md / CLAUDE.md managed blocks, .goals/goal-*.md.
Boundaries: no GPU/CUDA builds, no model downloads, no docker build or push,
no network calls from code paths under test, no credentials, no purchases,
no deploys. Navigate the workspace ICM-style (IDENTITY → CONTEXT → contract →
named inputs); never crawl the tree.

Write ALL scratch — notes, critic transcripts, spec corrections, progress
page, probes — into .goals/, never the repo root.

Stop after 20 tries. If still failing, stop, revert the failing piece's files
(repo root + its stage output), keep the last all-green `icm audit` state, and
report which check is failing and what was tried.
