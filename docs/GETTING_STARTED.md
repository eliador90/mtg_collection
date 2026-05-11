# Getting Started

This guide is for someone using the project for the first time.

## Short Version

1. Export your collection from ManaBox as a CSV.
2. Put that CSV in `data/private/`.
3. Run `mtg-collection scan`.
4. Pick a commander from `data/output/commander_candidates.csv`.
5. Run `mtg-collection build`.
6. Open the generated HTML deck viewer.

## Step 1: Install

From the project folder:

```bash
python -m venv .venv
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

## Step 2: Add Your Collection

Put your ManaBox CSV in:

```text
data/private/
```

Example:

```text
data/private/my_manabox_collection.csv
```

## Step 3: Scan It

```bash
mtg-collection scan --input data/private/my_manabox_collection.csv
```

This creates:

- `data/output/collection_enriched.csv`
- `data/output/commander_candidates.csv`
- `data/output/analysis/`

Open `data/output/commander_candidates.csv` and choose a commander.

## Step 4: Build A Deck

```bash
mtg-collection build --commander "Your Commander Name"
```

You can add a theme hint:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells"
```

Theme hints are plain text. They are not a fixed command list. Use short phrases with card-game words, such as:

- `artifact tokens`
- `graveyard recursion`
- `instant speed control`
- `angel lifegain`
- `faerie tempo`

The local builder uses these words as scoring hints, so direct phrases work better than long natural-language requests.

This creates:

- `data/output/<commander_and_theme>/<commander_and_theme>_deck.json`
- `data/output/<commander_and_theme>/<commander_and_theme>_deck.html`
- `data/output/<commander_and_theme>/<commander_and_theme>_ai_prompt.md`
- `data/output/<commander_and_theme>/<commander_and_theme>_validation.txt`
- `data/output/<commander_and_theme>/<commander_and_theme>_next_steps.txt`

Open the `.html` file in your browser.

The deck JSON file is the project's working deck file. The viewer, review command, export command, and manual AI workflow all use it.

Simple file guide:

- `_deck.json`: use this in commands
- `_deck.html`: open this in your browser
- `_ai_prompt.md`: paste this into Codex, Claude Code, ChatGPT, Claude, or another assistant
- `_tuning.json`: created by review and stores suggested swaps
- `_next_steps.txt`: exact follow-up commands for this deck

## Step 5: Keep Working

Ask for possible swaps:

```bash
mtg-collection review --folder data/output/my_deck
```

This also updates the deck HTML file, so you can review suggested swaps in the browser viewer.

If you prefer, you can still point directly at the deck JSON:

```bash
mtg-collection review --deck data/output/my_deck/my_deck_deck.json
```

Export to ManaBox:

```bash
mtg-collection export --folder data/output/my_deck --format manabox
```

Export to plain text:

```bash
mtg-collection export --folder data/output/my_deck --format text
```

## Optional AI Help

The build command creates an AI prompt file. You can paste that prompt into Codex, Claude Code, ChatGPT, Claude, or another assistant.

The prompt includes a filtered candidate pool from your collection. If you want the assistant to inspect the whole collection, upload the enriched CSV manually too. Only do that if you are comfortable sharing it with that assistant.

After saving an AI-refined deck JSON, compare it to the original:

```bash
mtg-collection review \
  --deck data/output/my_deck_refined/my_deck_refined_deck.json \
  --compare-to data/output/my_deck/my_deck_deck.json
```

You can also opt into direct OpenAI API generation:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --provider openai
```

This requires `OPENAI_API_KEY` and may cost money through the OpenAI API.

## Common Problems

### Python says a package is missing

Make sure your virtual environment is active, then run:

```bash
pip install -r requirements.txt
```

### The scan command says columns are missing

Check that the ManaBox export includes:

- `Name`
- `Quantity`
- `Scryfall ID`

### The deck builder cannot find the commander

Use the exact name from `data/output/commander_candidates.csv`.

### I use Windows and activation fails

PowerShell script execution rules can block virtual environment activation. You can still run commands with the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then try:

```powershell
mtg-collection --help
```
