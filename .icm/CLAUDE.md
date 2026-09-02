# Claude Code adapter — breeze-tts-runpod

Pointer file. The catalog is `IDENTITY.md` (Layer 0) and `CONTEXT.md` (Layer 1);
this file only tells an agent how to behave here. Keep it short — if it grows,
the payload belongs on a shelf, not in the catalog.

Form: **pipeline**

When working in this workspace:
- Read `IDENTITY.md`, then `CONTEXT.md`. Route from there; do not crawl the tree.
- Load only the Layer 3/4 files the current contract's **Inputs** table names.
- Every output is an edit surface: stop at the human check, let a person edit,
  then read whatever they left there.
- Run `icm audit` before finishing and `icm sync` whenever the structure changes.
