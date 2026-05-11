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

The deck build command creates prompt files automatically unless you pass `--no-prompt`.

## Sample Data

Public examples should be tiny and synthetic. Do not copy your real collection into `data/sample/`.

## API Features

The default workflow is local and does not call paid AI APIs.

If you use `--provider openai`, the project sends collection-derived deckbuilding context to OpenAI. That includes:

- commander details
- the local draft deck JSON
- selected candidate cards from the enriched collection
- theme hint, if provided

The project does not intentionally send the full raw ManaBox CSV, but candidate cards can still reveal parts of your collection.

API keys should stay in environment variables such as `OPENAI_API_KEY`. Do not put real keys in Git.
