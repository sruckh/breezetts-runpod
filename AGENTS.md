# AGENTS.md

Instructions for AI coding agents working in this project.

## Project layout

- `.icm/` — ICM pipeline workspace (form: pipeline, domain: breeze-tts-runpod)
  specifying the BreezeTTS RunPod serverless worker: 6 stages
  (discovery → validation → engine → handler/storage → container → tests),
  stable specs in `.icm/references/`, rules in `.icm/_config/`. Enter via
  `.icm/IDENTITY.md` then `.icm/CONTEXT.md`; do not crawl the tree.
- `.goals/` — goal briefs and agent scratch notes (kept out of the repo root).

<!-- outline:global-rules (managed by the outline skill) -->
## Global Agent Rules

The shared Global Agent Rules for this brain are imported below. They are
refreshed from Outline into `.outline/global-rules.md` at session start — edit
them in the Outline "Global Agent Rules" page, not here.

@.outline/global-rules.md
<!-- /outline:global-rules -->
