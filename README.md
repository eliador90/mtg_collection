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

`--theme` is optional; see [Theme Hints](#theme-hints) for what to put there.

Open the generated HTML deck viewer in the new deck folder under `data/output/`.

Commands use the `_deck.json` file. Your browser opens the `_deck.html` file.

## What It Creates

The scan command creates:

- `data/output/collection_enriched.csv`
- `data/output/commander_candidates.csv`
- `data/output/analysis/`

The build command creates:

- `<deck_name>_deck.json`: the project working file for this deck
- `<deck_name>_deck.html`: the browser viewer
- `<deck_name>_validation.txt`: legality and deck-shape checks
- `<deck_name>_ai_prompt.md`: a prompt you can paste into Codex, Claude Code, ChatGPT, Claude, or another assistant
- `<deck_name>_next_steps.txt`: exact follow-up commands for this deck

Each deck build gets its own folder, for example:

```text
data/output/jhoira_of_the_ghitu_suspend_big_spells/
  jhoira_of_the_ghitu_suspend_big_spells_deck.json
  jhoira_of_the_ghitu_suspend_big_spells_deck.html
```

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
| Review a deck | `mtg-collection review --folder data/output/my_deck` |
| Export a deck | `mtg-collection export --folder data/output/my_deck --format manabox` |
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

### Theme Hints

`--theme` is a plain-language hint, not a command list. Short concrete phrases work best:

```bash
--theme "artifact tokens"
--theme "graveyard recursion"
--theme "instant speed control"
--theme "angel lifegain"
```

The local builder looks for recognizable words in the theme and in card text, then nudges scoring toward matching cards. Anything goes, but very poetic prompts are less useful than direct card-game terms.

Add `--manabox` or `--text` if you want exports created at the same time:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --manabox \
  --text
```

### Review A Deck

Use the deck folder if you want the project to find the deck JSON for you:

```bash
mtg-collection review --folder data/output/jhoira_of_the_ghitu_suspend_big_spells
```

Or point directly at the deck JSON:

```bash
mtg-collection review --deck data/output/jhoira_of_the_ghitu_suspend_big_spells/jhoira_of_the_ghitu_suspend_big_spells_deck.json
```

This prints possible swaps from your collection, saves `<deck_name>_tuning.json`, writes those suggestions into the deck JSON, and regenerates the HTML viewer so you can review the swaps in the browser.

For your local files, the distinction is:

- `_deck.json`: use this in commands
- `_deck.html`: open this in your browser
- `_ai_prompt.md`: paste this into Codex, Claude Code, ChatGPT, Claude, or another assistant
- `_tuning.json`: saved swap suggestions from `review`
- `_next_steps.txt`: exact commands for the deck folder

To compare an edited deck with an older version:

```bash
mtg-collection review \
  --deck data/output/jhoira_refined/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_of_the_ghitu_suspend_big_spells/jhoira_of_the_ghitu_suspend_big_spells_deck.json
```

### Export A Deck

ManaBox-style CSV:

```bash
mtg-collection export \
  --folder data/output/jhoira_of_the_ghitu_suspend_big_spells \
  --format manabox
```

Plain text decklist:

```bash
mtg-collection export \
  --folder data/output/jhoira_of_the_ghitu_suspend_big_spells \
  --format text
```

### Manual AI Workflow

The build command creates an AI prompt file. Paste that prompt into Codex, Claude Code, ChatGPT, Claude, or another assistant and ask it to refine the deck JSON.

After you save the refined JSON in `data/output/`, run:

```bash
mtg-collection review \
  --deck data/output/jhoira_refined/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_of_the_ghitu_suspend_big_spells/jhoira_of_the_ghitu_suspend_big_spells_deck.json
```

Then open or regenerate the deck viewer.

This manual workflow uses your normal assistant and does not call paid AI APIs.

The AI prompt includes a filtered candidate pool from your collection, not necessarily the full CSV. If you want the assistant to search the whole collection, manually upload the enriched CSV too. Only do that if you are comfortable sharing collection-derived data with that assistant.

### Optional OpenAI API Provider

The default build is free and local. If you want the project to call OpenAI directly, set an API key and opt in:

```bash
export OPENAI_API_KEY=your_api_key_here
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --provider openai
```

Windows PowerShell uses `$env:OPENAI_API_KEY="your_api_key_here"`.

OpenAI API usage may cost money. A normal ChatGPT subscription does not automatically cover API usage. You can choose a model with `--model` or `OPENAI_MODEL`; otherwise the project uses the default in `.env.example`.

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
- It does not call paid AI APIs unless you explicitly use an API provider such as `--provider openai`.
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
