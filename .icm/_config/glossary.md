# Config — Glossary

> Layer 3 · factory. Shared vocabulary; use these terms exactly.

- **Voice Clone** — zero-shot speaker cloning from base64 reference audio
  plus its exact transcript.
- **Voice Design** — reference-free synthesis from a natural-language voice
  description; `--cfg-scale 4` baseline.
- **Voice Direction** — reference identity preserved; instruction steers
  tone, emotion, pace, delivery.
- **Vocal events** — inline non-speech cues: `(laugh)`, `(cough)`,
  `(clears throat)`, `(sigh)`; Chinese: `[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`.
- **CFG scale** — classifier-free guidance scale controlling instruction
  adherence.
- **`--fast-all`** — modular CUDA Graphs acceleration profile (~14.4 GiB
  VRAM vs ~7.7 GiB eager).
- **Presigned URL** — time-limited S3 GET URL (default 24 h) returned
  instead of inline audio.
- **`AUDIO_DELIVERY`** — `auto | s3 | base64` delivery selector.
- **Module-scope bootstrap** — model loads at import time, never per job.
- **B2 checksum fix** — botocore `when_required` checksum config required
  for Backblaze B2.
- **`MAX_REFERENCE_AUDIO_BYTES`** — 4 MB per decoded reference clip.
- **`MAX_TOTAL_REFERENCE_AUDIO_BYTES`** — 6 MB total decoded reference audio
  per request.
