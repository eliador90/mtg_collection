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

This creates:

- `data/output/<commander>_deck.json`
- `data/output/<commander>_deck.html`
- `data/output/<commander>_ai_prompt.md`
- `data/output/<commander>_validation.txt`

Open the `.html` file in your browser.

## Step 5: Keep Working

Ask for possible swaps:

```bash
mtg-collection review --deck data/output/my_deck_deck.json
```

Export to ManaBox:

```bash
mtg-collection export --deck data/output/my_deck_deck.json --format manabox
```

Export to plain text:

```bash
mtg-collection export --deck data/output/my_deck_deck.json --format text
```

## Optional AI Help

The build command creates an AI prompt file. You can paste that prompt into Codex, Claude Code, ChatGPT, Claude, or another assistant.

After saving an AI-refined deck JSON, compare it to the original:

```bash
mtg-collection review \
  --deck data/output/my_deck_refined_deck.json \
  --compare-to data/output/my_deck_deck.json
```

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
