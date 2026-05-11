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
Outputs are grouped in one folder, such as `data/output/jhoira_of_the_ghitu_suspend_big_spells/`.
The folder also contains `<deck_name>_next_steps.txt` with exact follow-up commands.

`--theme` is a plain-text hint. Good examples are `artifact tokens`, `graveyard recursion`, `instant speed control`, and `angel lifegain`.

### 3. Review

```bash
mtg-collection review --folder data/output/jhoira_of_the_ghitu_suspend_big_spells
```

This suggests possible swaps from your collection and updates the deck viewer so the swaps can be reviewed visually.

Use `_deck.json` in commands and open `_deck.html` in your browser. The `--folder` option lets the command find the deck JSON automatically.

### 4. Export

```bash
mtg-collection export --folder data/output/jhoira_of_the_ghitu_suspend_big_spells --format manabox
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
  --deck data/output/jhoira_refined/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_of_the_ghitu_suspend_big_spells/jhoira_of_the_ghitu_suspend_big_spells_deck.json
```

Choose a different collection file:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --collection data/output/another_collection_enriched.csv
```

Use the optional OpenAI API provider:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --provider openai
```

This requires `OPENAI_API_KEY` and may create API charges. Use `--model` if you want to choose a specific OpenAI model.

## Advanced Commands

The older individual commands still exist for scripting and development. See [Advanced commands](ADVANCED_COMMANDS.md).
