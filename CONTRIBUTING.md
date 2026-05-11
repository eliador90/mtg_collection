# Contributing

Thanks for considering a contribution. This project is intentionally small and practical, so clear improvements are very welcome.

## Before You Start

Please keep user privacy in mind:

- Do not commit real ManaBox exports.
- Do not commit generated files from `data/output/`.
- Do not add screenshots or examples that reveal a private collection unless the data is clearly synthetic.
- Use `data/sample/` only for tiny public examples.

Check before committing:

```bash
git status --short
```

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

On Windows PowerShell:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional EDHREC-style enrichment:

```bash
pip install -r requirements-optional.txt
```

## Checks

Run:

```bash
python -m unittest discover -s tests
python -m compileall src
```

If you change deck generation, also run a sample command:

```bash
mtg-build-commander-deck \
  --commander "Shorikai, Genesis Engine" \
  --collection data/sample/collection_enriched_sample.csv \
  --name sample_generated \
  --target-size 8
```

This writes files under `data/output/sample_generated/`, including `sample_generated_deck.json`.

## Pull Request Guidelines

- Keep changes focused.
- Explain why the change helps users.
- Add or update docs when behavior changes.
- Add tests for new behavior when practical.
- Avoid large generated files in pull requests.

## Good First Issues

- Improve setup instructions for a specific operating system.
- Add a small synthetic sample collection.
- Improve role detection in local deck generation.
- Improve deck JSON validation rules and warnings.
- Improve error messages for missing columns or missing commanders.
