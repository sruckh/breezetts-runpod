# Stage 06 — verification-and-test-suite

> Layer 2 · "What do I do?" — the control point of the whole system.

**Purpose:** Define the test suite: all 3 modes, vocal events, S3 presigned URL upload mocking, base64 fallback, payload limit enforcement, and RunPod local mock testing.

One job: define verification. This stage consumes every prior spec and
produces the suite that proves them.

## Inputs
| Kind | File/Location | Scope | Why |
|------|---------------|-------|-----|
| working | ../05-container-and-dockerfile/output/ | full | the container the suite runs against |
| reference | ../../references/payload-contracts.md | all | acceptance shapes + limits |
| reference | ../../references/s3-storage.md | all | delivery behaviour to mock |
| reference | ../../references/runpod-invariants.md | local testing | `--test_input` harness |

Exact paths only. **working** = this run (product, L4). **reference** = every
run (factory, L3). Anything not listed here is not loaded.

## Process
1. Read the inputs above — only those.
2. Define golden-payload tests for each mode: clone, design, direction.
3. Define vocal-event tests covering all 8 cues (4 English + 4 Chinese) as
   passthrough.
4. Define storage tests: S3 upload + presign with a mocked client (no
   network), asserting the B2 checksum config, key template, and all 7
   response fields; plus the base64 fallback when credentials are absent.
5. Define limit tests at the boundaries: 4 MB per clip, 6 MB total decoded —
   accept at the bound, reject one byte over.
6. Define the RunPod local harness: `python3 handler.py --test_input '<json>'`
   per mode, and the container smoke check against the stage 05 spec.
7. Write the test plan to `output/`.

## Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Test suite plan | output/verification-and-test-suite.md | markdown |

## Human check
For each audit box in stages 02–05, point at the test that would catch its
violation; any box without a test is a gap to close. Edit in place.

## Audits
- [ ] All 3 modes have golden payloads
- [ ] All 8 vocal events exercised
- [ ] S3 tests fully mocked — no network, no real credentials
- [ ] Boundary tests at exactly 4 MB / 6 MB and one byte over
- [ ] `--test_input` local run documented per mode
- [ ] Crash-dump behaviour asserted (logs to stdout, no secrets)
