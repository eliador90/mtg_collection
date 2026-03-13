# MTG Collection Project

Python tools for analyzing a Magic: The Gathering collection exported from ManaBox, with a focus on Commander deckbuilding workflows.

License: MIT. See [LICENSE](LICENSE).

## Project Overview

This repository helps you:

- read a ManaBox collection export
- enrich the collection with Scryfall metadata
- optionally add EDHREC-style commander data
- identify likely commander candidates in the collection
- generate simple collection summaries that are useful for Commander analysis

The project is designed to be reusable by other people with their own ManaBox CSV exports.

## Current Features

- Scryfall enrichment from a ManaBox CSV that includes `Scryfall ID`
- Optional EDHREC enrichment layer that fails gracefully if the dependency or data source is unavailable
- Commander candidate detection based on:
  - legendary creatures that are legal in Commander
  - cards whose rules text says they can be your commander
- Simple collection analysis:
  - color identity distribution
  - type distribution
  - candidate commander counts
  - total cards and unique card counts

## Planned Future Features

- Archetype clustering
- Deck shell suggestions
- Commander support scoring
- Upgrade recommendation logic
- Basic deck generation

## Folder Structure

```text
mtg_collection_project/
├── data/
│   ├── output/         # generated files, ignored by Git
│   ├── private/        # your real collection exports, ignored by Git
│   └── sample/         # tiny public sample files
├── src/                # CLI scripts and shared helpers
├── .gitignore
├── README.md
└── requirements.txt
```

## Privacy Model

Your real collection files should stay in `data/private/`.

This repository is set up so that:

- `data/private/` is ignored by Git
- `data/output/` is ignored by Git
- the two known local collection filenames are explicitly ignored

That makes the repository much safer to publish on GitHub without uploading your real collection data.

## Setup

### Ubuntu / WSL (recommended)

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Windows PowerShell

If you work in PowerShell instead of Ubuntu/WSL, create a separate Windows virtual environment:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Do not share the same `.venv` between Ubuntu/WSL and Windows PowerShell. Create it inside the environment you plan to use.

## Input Expectations

The Scryfall enrichment script expects a ManaBox CSV with at least these columns:

- `Name`
- `Quantity`
- `Scryfall ID`

## Usage

### 1. Enrich a ManaBox export with Scryfall

```bash
python src/enrich_scryfall.py \
  --input data/private/ManaBox_Collection_Final_20260312.csv \
  --output data/output/collection_enriched.csv
```

### 2. Optionally enrich commander candidates with EDHREC data

```bash
python src/enrich_edhrec_optional.py \
  --input data/output/collection_enriched.csv \
  --output data/output/collection_enriched_with_edhrec.csv
```

Notes:

- This step is optional.
- EDHREC has no official public API for this workflow.
- The script is written to fail gracefully and keep the main Scryfall-based workflow usable.

### 3. Identify likely commanders in the collection

```bash
python src/identify_commanders.py \
  --input data/output/collection_enriched.csv \
  --output data/output/commander_candidates.csv
```

### 4. Analyze the collection

```bash
python src/analyze_collection.py \
  --input data/output/collection_enriched.csv \
  --output-dir data/output/analysis
```

## Sample Files

Public sample files live in `data/sample/`.

- `manabox_collection_sample.csv` is a tiny ManaBox-style example
- `collection_enriched_sample.csv` is a tiny enriched example for testing downstream scripts without your real collection

Example commands with sample data:

```bash
python src/identify_commanders.py \
  --input data/sample/collection_enriched_sample.csv \
  --output data/output/sample_commanders.csv

python src/analyze_collection.py \
  --input data/sample/collection_enriched_sample.csv \
  --output-dir data/output/sample_analysis
```

### Windows path note

If you prefer PowerShell, use backslashes in paths and the PowerShell activation command instead. The script arguments are otherwise the same.

## Notes for GitHub Publication

Before pushing this repository:

1. Confirm your real CSV files are inside `data/private/`.
2. Confirm `git status` does not show private collection files.
3. Review any sample files to make sure they are safe to publish.
4. Commit only source code, documentation, and safe sample files.

## License

This project is released under the MIT License. See `LICENSE`.

## Roadmap

This first version focuses on clean structure and reusable scripts. Future iterations can add stronger Commander-specific logic, better deck support metrics, and deck generation helpers.
