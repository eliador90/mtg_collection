# Beginner Command Overview

Use `mtg-collection` for normal day-to-day use.

```bash
mtg-collection --help
```

## The Main Flow

### 1. Scan

```bash
mtg-collection scan --input data/private/my_manabox_collection.csv
```

This creates the enriched collection file and commander candidate list.

### 2. Build

```bash
mtg-collection build --commander "Jhoira of the Ghitu" --theme "suspend big spells"
```

This creates the deck JSON, HTML viewer, validation report, and AI prompt.

### 3. Review

```bash
mtg-collection review --deck data/output/jhoira_of_the_ghitu_deck.json
```

This suggests possible swaps from your collection. It does not edit your deck automatically.

### 4. Export

```bash
mtg-collection export --deck data/output/jhoira_of_the_ghitu_deck.json --format manabox
```

Use `--format text` for a plain text decklist.

## Command Reference

| Command | Use it when |
| --- | --- |
| `mtg-collection scan` | You have a fresh ManaBox collection CSV |
| `mtg-collection commanders` | You already have an enriched CSV and only want the commander list |
| `mtg-collection build` | You picked a commander and want a deck draft |
| `mtg-collection review` | You want tuning suggestions or a before/after comparison |
| `mtg-collection export` | You want ManaBox CSV or plain text output |
| `mtg-collection import-deck` | You want to bring a ManaBox-style deck CSV into this project |
| `mtg-collection privacy-check` | You want to check that private/output files are not tracked |

## Useful Options

Build and create exports at the same time:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --manabox \
  --text
```

Compare a refined deck to the original:

```bash
mtg-collection review \
  --deck data/output/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_of_the_ghitu_deck.json
```

Choose a different collection file:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --collection data/output/another_collection_enriched.csv
```

## Advanced Commands

The older individual commands still exist for scripting and development. See [Advanced commands](ADVANCED_COMMANDS.md).
