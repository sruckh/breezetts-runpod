# Scaffold notes — breeze-tts-runpod ICM workspace

Executed `.goals/goal-scaffold-breezetts-icm.md` on 2026-09-01.

- Scaffolded: `icm new .icm --domain breeze-tts-runpod --form pipeline`.
- 6 stages added via `icm stage`, contracts fully rewritten with real
  Inputs/Process/Outputs tables, human checks, and audit boxes.
- Layer 3 populated: `references/` (breezetts-architecture, s3-storage,
  runpod-invariants, payload-contracts) and `_config/` (conventions,
  glossary, voice).
- `icm sync` regenerated the stage catalog in `.icm/CONTEXT.md`.
- **Result: `icm audit .icm --strict` → exit 0, 0 violations, 0 warnings,
  first attempt** (budget was 6).
- DOX: root `AGENTS.md` gained a Project layout section covering `.icm/` and
  `.goals/`.

Next: walk the pipeline with `icm run .icm --stage 1`, stopping at each
stage's human check.
