# Deck Generation Architecture

This project uses a staged deck-generation workflow so it stays useful for people who do not want paid AI calls, while leaving a clean path for optional AI providers later.

## Design Goals

- Keep private collection CSVs local.
- Always produce the same deck JSON format that the viewer already understands.
- Make the free local workflow useful on its own.
- Make AI optional, replaceable, and easy to explain.
- Validate generated decks after any local or AI step.

## Recommended Flow

```text
ManaBox CSV
  -> mtg-collection scan
  -> mtg-collection build
  -> mtg-collection review/export
```

The lower-level implementation still uses this pipeline:

```text
ManaBox CSV
  -> enrich_scryfall.py
  -> build_commander_deck.py
  -> validate_deck.py
  -> optional tune_deck.py / compare_decks.py
  -> optional manual AI refinement or future API provider
  -> generate_deck_viewer.py
```

## Current Local Components

### `src/mtg_collection_cli.py`

Beginner-facing wrapper command. It exposes a small set of workflow verbs:

- `scan`
- `commanders`
- `build`
- `review`
- `export`
- `import-deck`
- `privacy-check`

This is the recommended public entrypoint for most users.

### `src/deck_generation.py`

Reusable deck-generation logic:

- loads an enriched collection CSV
- finds the requested commander
- filters cards by Commander color identity
- groups cards into rough deck roles
- scores cards with a transparent heuristic
- fills the mana base with legal nonbasics plus basic lands
- writes deck JSON compatible with the viewer
- can export an AI-ready prompt for manual refinement

### `src/build_commander_deck.py`

Beginner-facing command-line entrypoint. This is the recommended workflow for most users.

Example:

```bash
python src/build_commander_deck.py \
  --commander "Jhoira of the Ghitu" \
  --collection data/output/collection_enriched.csv \
  --name jhoira \
  --theme "suspend big spells"
```

It generates:

- deck JSON
- HTML viewer
- AI-ready prompt
- validation report

The deck JSON also stores local draft quality notes under `generation.quality`. When validation runs, the structured report is stored under `refinement.validation_report` so the HTML viewer can show it.

### `src/generate_deck_draft.py`

Lower-level entrypoint for users or future provider work that only need a deck JSON and optional prompt/viewer outputs.

### `src/validate_deck.py`

Checks a deck JSON against an enriched collection CSV:

- deck size
- commander shape and legality metadata
- color identity
- singleton rule
- missing cards
- basic deck shape warnings

### `src/tune_deck.py`

Suggests reviewable swaps for an existing deck JSON. It uses the same local scoring ideas as deck generation, looks at validation warnings, and proposes cards from the enriched collection.

This command intentionally does not edit the deck automatically. It produces a printed report and, optionally, a JSON report so users can decide which changes they want.

### `src/compare_decks.py`

Compares two project deck JSON files and reports:

- added cards
- removed cards
- count increases and decreases
- category changes

This is useful after manual edits or AI-assisted refinement.

### `src/deck_providers.py`

Provider interface for local and future AI-backed deck drafting.

Current provider:

- `local`

Planned extension points:

- `openai`
- `anthropic`
- `openrouter`
- `ollama`

### `src/deck_io.py`

Reusable import/export helpers for ManaBox-style deck CSVs.

Related commands:

- `src/export_deck_manabox.py`
- `src/import_manabox_deck.py`
- `src/export_deck_text.py`

## Manual AI Workflow

The `--prompt-output` file is designed for Codex, Claude Code, ChatGPT, Claude, or another assistant.

This avoids API cost:

1. Run the local draft command.
2. Open the generated prompt Markdown file.
3. Paste it into the assistant of choice.
4. Ask the assistant to return the same deck JSON format.
5. Save the refined JSON.
6. Validate it.
7. Run the viewer.

## Future API Provider Workflow

API-based generation should reuse the same pipeline:

```text
local candidate pool
  -> provider adapter
  -> returned deck JSON
  -> local validator
  -> viewer
```

Suggested provider interface:

```python
class DeckDraftProvider:
    name: str

    def draft_deck(self, request: DeckDraftRequest) -> dict:
        ...
```

Provider adapters should live separately from the local heuristic. For example:

- `OpenAIProvider`
- `AnthropicProvider`
- `OpenRouterProvider`
- `OllamaProvider`

Each provider should receive a small, filtered candidate pool instead of the full collection CSV.

## Validation Layer

A validator should run after both local and AI generation. It should check:

- deck has exactly the requested size
- commander exists
- no illegal color-identity cards are included
- singleton rules are respected except for basic lands
- all main-deck cards are either in the collection or intentionally marked as external upgrades
- required deck JSON keys are present

The validator is now the stricter gate before publishing API-based generation. Future provider adapters should run generated JSON through the validator before rendering or recommending it.

The HTML viewer renders `refinement.validation_report` when present, so users can see errors and warnings without opening the text report separately.

## UX Principles

- Default command should work without API keys.
- API keys should never be committed and should be read from environment variables.
- Errors should say what the user can do next.
- Generated files should go to `data/output/`.
- Real collection exports should stay in `data/private/`.
- Any AI feature should be opt-in and visibly labeled as paid or provider-dependent.
