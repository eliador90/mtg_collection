# Advanced Commands

Most users should start with `mtg-collection`. This page lists the lower-level commands for scripting, debugging, or development.

Every installed command supports `--help`.

## Individual Commands

| What you want | Installed command | Script command |
| --- | --- | --- |
| Enrich a ManaBox export with Scryfall data | `mtg-enrich-scryfall` | `python src/enrich_scryfall.py` |
| Find Commander candidates | `mtg-identify-commanders` | `python src/identify_commanders.py` |
| Analyze collection summaries | `mtg-analyze-collection` | `python src/analyze_collection.py` |
| Build a Commander deck draft end to end | `mtg-build-commander-deck` | `python src/build_commander_deck.py` |
| Generate only a deck draft JSON | `mtg-generate-deck-draft` | `python src/generate_deck_draft.py` |
| Validate a deck JSON | `mtg-validate-deck` | `python src/validate_deck.py` |
| Suggest reviewable tuning swaps | `mtg-tune-deck` | `python src/tune_deck.py` |
| Compare two deck JSON files | `mtg-compare-decks` | `python src/compare_decks.py` |
| Render a deck viewer from JSON | `mtg-generate-deck-viewer` | `python src/generate_deck_viewer.py` |
| Export deck to ManaBox-style CSV | `mtg-export-deck-manabox` | `python src/export_deck_manabox.py` |
| Export deck to plain text | `mtg-export-deck-text` | `python src/export_deck_text.py` |
| Import ManaBox-style deck CSV | `mtg-import-manabox-deck` | `python src/import_manabox_deck.py` |
| Optional EDHREC-style enrichment | `mtg-enrich-edhrec` | `python src/enrich_edhrec_optional.py` |

## Full Manual Example

```bash
mtg-enrich-scryfall \
  --input data/private/my_manabox_collection.csv \
  --output data/output/collection_enriched.csv

mtg-identify-commanders \
  --input data/output/collection_enriched.csv \
  --output data/output/commander_candidates.csv

mtg-build-commander-deck \
  --commander "Jhoira of the Ghitu" \
  --collection data/output/collection_enriched.csv \
  --theme "suspend big spells"
```

The beginner equivalent is:

```bash
mtg-collection scan --input data/private/my_manabox_collection.csv
mtg-collection build --commander "Jhoira of the Ghitu" --theme "suspend big spells"
```

## Provider Option

Deck generation currently supports:

```bash
--provider local
--provider openai
```

OpenAI requires `OPENAI_API_KEY` and may cost money:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --provider openai \
  --model gpt-5.2
```

The project reserves these names for future providers:

- `anthropic`
- `openrouter`
- `ollama`

Those provider names are scaffolding only.
