# Privacy Guide

This project is built around local collection files. Treat those files as private unless you intentionally want to share them.

## Where Private Files Belong

Put real collection exports in:

```text
data/private/
```

Put generated analysis, deck drafts, prompts, and HTML viewers in:

```text
data/output/
```

Both folders are ignored by Git.

## Before Publishing Or Opening A Pull Request

Run:

```bash
mtg-collection privacy-check
```

Private collection files should not appear.

The command checks:

```bash
git ls-files data/private data/output
```

Only `.gitkeep` placeholders should be listed.

## Prompt Files

Prompt files generated with `--prompt-output` can include:

- commander details
- selected deck cards
- candidate cards from your collection

They are useful, but they may reveal parts of your collection. Keep them in `data/output/` unless you intentionally want to share them.

The one-command deck builder creates prompt files automatically unless you pass `--no-prompt`.

## Sample Data

Public examples should be tiny and synthetic. Do not copy your real collection into `data/sample/`.

## Future API Features

The current project does not call paid AI APIs.

If API-based generation is added later, it should:

- send only a filtered candidate pool, not the full raw collection
- clearly explain what is sent to the provider
- keep API keys out of Git
- make networked AI generation opt-in
