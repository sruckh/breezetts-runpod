# Stage 01 — discovery-and-contracts

> Layer 2 · "What do I do?" — the control point of the whole system.

**Purpose:** Pin Breeze TTS 2 architecture, upstream APIs, audio format, Backblaze B2 S3 delivery schemas, and RunPod payload limits into stable contracts.

One job: discover and pin facts. This stage does not design validation,
engine, handler, container, or tests — later stages consume what is pinned
here.

## Inputs
| Kind | File/Location | Scope | Why |
|------|---------------|-------|-----|
| working | ../../../.goals/goal-scaffold-breezetts-icm.md | full | the build brief this workspace executes |
| reference | ../../_config/conventions.md | all | factory rules every contract must obey |
| reference | ../../_config/glossary.md | all | shared vocabulary for pinned terms |

Exact paths only. **working** = this run (product, L4). **reference** = every
run (factory, L3). Anything not listed here is not loaded.

## Process
1. Read the inputs above — only those.
2. Extract every load-bearing fact from the brief: modes, vocal events,
   audio format, VRAM budgets, S3 response fields, payload limits, RunPod
   invariants.
3. Resolve each fact against upstream sources (Breeze TTS repo/docs, RunPod
   docs, Backblaze B2 docs); pin exact versions, numbers, and flag names.
4. Write/refresh the four pinned fact sheets in `../../references/`.
5. Write the run-level contract summary to `output/`.

Keep this numbered and short. Constraints live in the reference files, not
restated here.

## Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Pinned fact sheets | ../../references/*.md | markdown |
| Contract summary | output/discovery-and-contracts.md | markdown |

## Human check
Read the contract summary and confirm every number (kHz, MB, GiB, seconds)
matches the brief and upstream docs. Edit in place; the next stage reads
whatever is here.

## Audits
- [ ] Audio format pinned: 24 kHz mono 16-bit PCM WAV
- [ ] All three modes and both vocal-event syntaxes pinned
- [ ] VRAM budgets pinned: eager ~7.7 GiB, `--fast-all` ~14.4 GiB
- [ ] S3 response fields, key template, and B2 checksum fix pinned verbatim
- [ ] RunPod invariants complete: module-scope bootstrap, static scanner,
      `ENTRYPOINT []`, `RUNPOD_INIT_TIMEOUT=1200`, `/runpod-volume`, crash dumps
- [ ] Payload limits pinned: 4 MB per clip, 6 MB total decoded
