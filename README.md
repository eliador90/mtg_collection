# MTG Collection Commander Toolkit

Local Python tools for turning a ManaBox collection CSV into Commander ideas, deck drafts, and simple HTML deck viewers.

The default workflow is private and local: your real collection stays on your machine, and generated files are ignored by Git.

## Quick Start

Install once from the project folder:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

macOS, Linux, or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Put your ManaBox collection CSV in:

```text
data/private/
```

## Normal Workflow

1. Scan your collection:

   ```bash
   mtg-collection scan --input data/private/my_manabox_collection.csv
   ```

2. Open the commander list:

   ```text
   data/output/commander_candidates.csv
   ```

3. Pick a commander and build a deck:

   ```bash
   mtg-collection build --commander "Jhoira of the Ghitu" --theme "suspend big spells"
   ```

4. Open the generated HTML viewer in the new deck folder under `data/output/`.

5. Ask for upgrade ideas:

   ```bash
   mtg-collection review --folder data/output/jhoira_of_the_ghitu_suspend_big_spells
   ```

The `review` command updates the HTML viewer, so reopen the viewer after running it.

## ChatGPT Or Claude Workflow

Use this when you want help from ChatGPT, Claude, Codex, or Claude Code in their normal web/app interface, without API billing.

1. Run the normal scan and build steps above.
2. Open the generated deck folder in `data/output/`.
3. Upload or paste the generated `<deck_name>_ai_prompt.md` into ChatGPT or Claude.
4. Optionally upload `data/output/collection_enriched.csv` too if you want the assistant to inspect more of your collection.
5. Ask the assistant to improve the deck and return a project-compatible deck JSON.
6. Save the refined JSON in `data/output/`.
7. Review or compare it with:

   ```bash
   mtg-collection review --deck data/output/my_refined_deck/my_refined_deck_deck.json
   ```

The generated prompt already includes a focused card pool from your collection. Uploading the full enriched CSV gives the assistant more context, but only do that if you are comfortable sharing collection-derived data with that service.

## Useful Commands

| Goal | Command |
| --- | --- |
| Scan a collection | `mtg-collection scan --input data/private/my_collection.csv` |
| Build a deck | `mtg-collection build --commander "Commander Name"` |
| Add a theme | `mtg-collection build --commander "Commander Name" --theme "artifact tokens"` |
| Find upgrades | `mtg-collection review --folder data/output/my_deck` |
| Export to ManaBox | `mtg-collection export --folder data/output/my_deck --format manabox` |
| Export text decklist | `mtg-collection export --folder data/output/my_deck --format text` |
| Check privacy | `mtg-collection privacy-check` |

`--theme` is just a plain-language hint. Good examples: `artifact tokens`, `graveyard recursion`, `instant speed control`, `angel lifegain`.

## File Guide

Each deck build gets its own folder, for example:

```text
data/output/jhoira_of_the_ghitu_suspend_big_spells/
```

Inside it:

- `_deck.json`: the working deck file used by commands
- `_deck.html`: the browser viewer
- `_ai_prompt.md`: prompt for ChatGPT, Claude, Codex, or Claude Code
- `_validation.txt`: basic deck checks
- `_tuning.json`: upgrade suggestions created by `review`
- `_next_steps.txt`: exact follow-up commands for that deck

Simple rule: use `_deck.json` in commands, open `_deck.html` in your browser.

## Privacy

Keep real collection files in `data/private/`. Generated files go in `data/output/`.

Both folders are ignored by Git except for `.gitkeep` placeholders. Before publishing a fork or opening a pull request, run:

```bash
mtg-collection privacy-check
```

The project does not call paid AI APIs unless you explicitly choose an API provider such as `--provider openai`. Normal ChatGPT or Claude web/app use is manual and separate from API billing.

## More Documentation

- [Getting started guide](docs/GETTING_STARTED.md)
- [Beginner command overview](docs/COMMANDS.md)
- [AI workflows](docs/AI_WORKFLOWS.md)
- [Privacy guide](docs/PRIVACY.md)
- [Advanced commands](docs/ADVANCED_COMMANDS.md)
- [Deck generation architecture](docs/DECK_GENERATION_ARCHITECTURE.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Development

```bash
python -m unittest discover -s tests
python -m compileall src tests
```

## License

MIT. See [LICENSE](LICENSE).
