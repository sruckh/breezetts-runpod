# Stage 05 — container-and-dockerfile

> Layer 2 · "What do I do?" — the control point of the whole system.

**Purpose:** Specify the Dockerfile: ENTRYPOINT [], unbuffered CMD, RUNPOD_INIT_TIMEOUT=1200, CUDA sm90/sm80 build configuration, and explicit package pinning.

One job: specify the container. This stage does not define runtime behaviour
(stages 03/04 did) or tests (stage 06 does).

## Inputs
| Kind | File/Location | Scope | Why |
|------|---------------|-------|-----|
| working | ../04-handler-and-storage/output/ | full | the code the container runs |
| reference | ../../references/runpod-invariants.md | container section | entrypoint, CMD, timeout rules |
| reference | ../../references/breezetts-architecture.md | inference profiles | CUDA/flash-attn build needs |
| reference | ../../references/s3-storage.md | dependencies | boto3 / botocore floor |

Exact paths only. **working** = this run (product, L4). **reference** = every
run (factory, L3). Anything not listed here is not loaded.

## Process
1. Read the inputs above — only those.
2. Choose the CUDA base image and specify the sm90/sm80 build configuration
   (incl. `flash-attn` compilation targets).
3. Pin every package explicitly: `boto3`, `botocore>=1.36`, `hf_transfer`,
   `flash-attn`, plus the Breeze TTS 2 stack pinned in stage 01.
4. Specify the environment: `RUNPOD_INIT_TIMEOUT=1200`, HF cache at
   `/runpod-volume`, unbuffered Python.
5. Specify the launch contract exactly: `ENTRYPOINT []` and
   `CMD ["python3", "-u", "handler.py"]`.
6. Write the Dockerfile spec to `output/`.

## Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Dockerfile spec | output/container-and-dockerfile.md | markdown |

## Human check
Read the spec as if reviewing a Dockerfile diff: every pin exact, every
invariant literal. Edit in place; the next stage reads whatever is here.

## Audits
- [ ] `ENTRYPOINT []` literal, not omitted
- [ ] `CMD ["python3", "-u", "handler.py"]` exact
- [ ] `RUNPOD_INIT_TIMEOUT=1200` set in the image
- [ ] sm90 and sm80 both covered; `flash-attn` pinned
- [ ] `boto3`, `botocore>=1.36`, `hf_transfer` pinned explicitly
