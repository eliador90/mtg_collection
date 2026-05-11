# MTG Collection Commander Toolkit

Local Python tools for turning a ManaBox collection export into Commander deck ideas, deck drafts, and shareable deck viewer pages.

The project is privacy-first: your real collection CSV stays on your machine, and generated files are ignored by Git by default.

## What Most Users Do

There are two main steps:

1. Scan your ManaBox collection.
2. Build a Commander deck from one of the commanders it finds.

After setup, the beginner workflow looks like this:

```bash
mtg-collection scan --input data/private/my_manabox_collection.csv
```

Then open:

```text
data/output/commander_candidates.csv
```

Pick a commander, then run:

```bash
mtg-collection build --commander "Jhoira of the Ghitu" --theme "suspend big spells"
```

Open the generated HTML deck viewer in `data/output/`.

## What It Creates

The scan command creates:

- `data/output/collection_enriched.csv`
- `data/output/commander_candidates.csv`
- `data/output/analysis/`

The build command creates:

- a deck JSON file
- an HTML deck viewer
- a validation report
- an AI-ready prompt you can paste into Codex, Claude Code, ChatGPT, Claude, or another assistant

## Setup

Python 3.10 or newer is recommended.

macOS, Linux, or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Windows PowerShell:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

Do not share the same `.venv` between WSL/Linux and Windows PowerShell.

## Beginner Commands

Use `mtg-collection` as the main command.

| Goal | Command |
| --- | --- |
| Scan a ManaBox collection | `mtg-collection scan --input data/private/my_collection.csv` |
| Rebuild commander candidates | `mtg-collection commanders` |
| Build a deck | `mtg-collection build --commander "Commander Name"` |
| Review a deck | `mtg-collection review --deck data/output/my_deck_deck.json` |
| Export a deck | `mtg-collection export --deck data/output/my_deck_deck.json --format manabox` |
| Check private files | `mtg-collection privacy-check` |

Every command supports `--help`:

```bash
mtg-collection build --help
```

## Common Workflows

### Scan Your Collection

Export your ManaBox collection as CSV and put it in:

```text
data/private/
```

Then run:

```bash
mtg-collection scan --input data/private/my_manabox_collection.csv
```

The ManaBox CSV must include:

- `Name`
- `Quantity`
- `Scryfall ID`

### Build A Deck

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells"
```

By default, this uses:

```text
data/output/collection_enriched.csv
```

Add `--manabox` or `--text` if you want exports created at the same time:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --manabox \
  --text
```

### Review A Deck

```bash
mtg-collection review --deck data/output/jhoira_of_the_ghitu_deck.json
```

This prints possible swaps from your collection and saves a tuning report. It does not edit your deck automatically.

To compare an edited deck with an older version:

```bash
mtg-collection review \
  --deck data/output/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_of_the_ghitu_deck.json
```

### Export A Deck

ManaBox-style CSV:

```bash
mtg-collection export \
  --deck data/output/jhoira_of_the_ghitu_deck.json \
  --format manabox
```

Plain text decklist:

```bash
mtg-collection export \
  --deck data/output/jhoira_of_the_ghitu_deck.json \
  --format text
```

### Manual AI Workflow

The build command creates an AI prompt file. Paste that prompt into Codex, Claude Code, ChatGPT, Claude, or another assistant and ask it to refine the deck JSON.

After you save the refined JSON in `data/output/`, run:

```bash
mtg-collection review \
  --deck data/output/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_of_the_ghitu_deck.json
```

Then open or regenerate the deck viewer.

This workflow uses your normal assistant manually. The project does not currently call paid AI APIs.

## Privacy

Your real collection files should stay in:

```text
data/private/
```

Generated files should go in:

```text
data/output/
```

Both folders are ignored by Git except for `.gitkeep` placeholders.

Before publishing your fork or opening a pull request, run:

```bash
mtg-collection privacy-check
```

## Advanced Commands

The project still includes individual expert commands such as `mtg-enrich-scryfall`, `mtg-build-commander-deck`, `mtg-validate-deck`, `mtg-tune-deck`, and `mtg-compare-decks`.

Most users do not need them. See [Advanced commands](docs/ADVANCED_COMMANDS.md) when you want lower-level control.

## More Documentation

- [Getting started guide](docs/GETTING_STARTED.md)
- [Beginner command overview](docs/COMMANDS.md)
- [Advanced commands](docs/ADVANCED_COMMANDS.md)
- [Privacy guide](docs/PRIVACY.md)
- [AI workflows](docs/AI_WORKFLOWS.md)
- [Deck generation architecture](docs/DECK_GENERATION_ARCHITECTURE.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security and privacy reporting](SECURITY.md)
- [Changelog](CHANGELOG.md)

## What It Is Not

- It is not a finished deckbuilding engine.
- It is not affiliated with Wizards of the Coast, ManaBox, Scryfall, EDHREC, or Cardmarket.
- It does not currently call paid AI APIs.
- It does not replace human deck tuning. The local deck draft is a starting point.

## Development

Run the smoke tests:

```bash
python -m unittest discover -s tests
```

Compile-check the scripts:

```bash
python -m compileall src tests
```

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
