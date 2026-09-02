# Config — Voice (spec style)

> Layer 3 · factory. How stage outputs must read.

- Declarative, imperative mood: "validate X before Y", not "you might want
  to".
- Schemas and field sets go in tables; exact values, never ranges or
  approximations, unless the reference itself is approximate (e.g. VRAM
  budgets marked `~`).
- Every load-bearing claim cites its `references/` file by name.
- Flag names, env vars, and constants in backticks, spelled exactly as code
  will spell them.
- No marketing language, no hedging; a spec is a contract.
