# Changelog

This project does not have formal releases yet. Notable changes are tracked here so users can understand the direction of the toolkit.

## Unreleased

- Added beginner-friendly `mtg-collection` workflow command with `scan`, `build`, `review`, `export`, `import-deck`, and `privacy-check` subcommands.
- Simplified beginner documentation and moved lower-level commands into advanced docs.
- Added local first-pass Commander deck generation.
- Added deck validation with errors and deck-shape warnings.
- Added validation and draft quality notes to generated deck viewers.
- Added one-command local deck build workflow.
- Added reviewable local deck tuning suggestions.
- Added deck diff/compare reports for before-and-after deck JSON files.
- Added ManaBox-style deck CSV import and export commands.
- Added plain text decklist export.
- Added provider interface scaffolding for future optional AI providers.
- Added installable console scripts through `pyproject.toml`.
- Added AI-ready prompt export for manual refinement in Codex, Claude Code, ChatGPT, Claude, or similar assistants.
- Added architecture notes for future optional API-based generation providers.
- Improved deck viewer fallback handling for generated cards and basic lands.
- Split optional EDHREC dependency into `requirements-optional.txt`.
- Added open-source project docs, issue templates, privacy notes, and smoke tests.
- Added command overview docs with installed `mtg-*` command names and slash-style workflow shorthand.
