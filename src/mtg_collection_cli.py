from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from analyze_collection import build_color_distribution, build_summary, build_type_distribution
from build_commander_deck import build_commander_deck, slugify
from deck_diff import compare_decks, format_diff_report, write_diff_json
from deck_io import export_deck_to_manabox_csv, import_manabox_deck_csv
from deck_providers import provider_names
from deck_text_export import export_deck_to_text
from deck_tuning import format_tuning_report, tune_deck
from mtg_collection_utils import (
    REQUIRED_MANABOX_COLUMNS,
    build_commander_candidate_table,
    ensure_columns,
    fetch_scryfall_cards_by_ids,
    normalize_scryfall_ids,
    read_csv_file,
)


DEFAULT_OUTPUT_DIR = "data/output"
DEFAULT_COLLECTION_PATH = "data/output/collection_enriched.csv"
DEFAULT_COMMANDERS_PATH = "data/output/commander_candidates.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mtg-collection",
        description="Beginner-friendly workflows for scanning a ManaBox collection and building Commander decks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Enrich a ManaBox CSV and find commander candidates.")
    scan.add_argument("--input", required=True, help="Path to your ManaBox collection CSV.")
    scan.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory. Defaults to data/output.")
    scan.add_argument("--sleep-seconds", type=float, default=0.12, help="Delay between Scryfall API batches.")
    scan.add_argument("--skip-analysis", action="store_true", help="Skip collection summary outputs.")
    scan.set_defaults(func=run_scan)

    commanders = subparsers.add_parser("commanders", help="Rebuild the commander candidate CSV from an enriched collection.")
    commanders.add_argument("--collection", default=DEFAULT_COLLECTION_PATH, help="Enriched collection CSV.")
    commanders.add_argument("--output", default=DEFAULT_COMMANDERS_PATH, help="Commander candidate CSV output.")
    commanders.set_defaults(func=run_commanders)

    build = subparsers.add_parser("build", help="Build a local Commander deck draft and viewer.")
    build.add_argument("--commander", required=True, help="Commander name to build around.")
    build.add_argument("--collection", default=DEFAULT_COLLECTION_PATH, help="Enriched collection CSV.")
    build.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory. Defaults to data/output.")
    build.add_argument("--name", default="", help="Optional filename stem. Defaults to the commander name.")
    build.add_argument("--theme", default="", help="Optional theme hint, such as 'suspend big spells'.")
    build.add_argument("--target-size", type=int, default=100, help="Deck size including commander. Defaults to 100.")
    build.add_argument("--land-count", type=int, default=None, help="Optional exact land count.")
    build.add_argument(
        "--provider",
        default="local",
        choices=provider_names(),
        help="Deck provider. Beginners should leave this as local.",
    )
    build.add_argument("--no-viewer", action="store_true", help="Skip HTML viewer generation.")
    build.add_argument("--no-prompt", action="store_true", help="Skip AI-ready prompt generation.")
    build.add_argument("--no-validate", action="store_true", help="Skip validation after generation.")
    build.add_argument("--manabox", action="store_true", help="Also export a ManaBox-style deck CSV.")
    build.add_argument("--text", action="store_true", help="Also export a plain text decklist.")
    build.set_defaults(func=run_build)

    review = subparsers.add_parser("review", help="Review a deck with tuning suggestions and optional comparison.")
    review.add_argument("--deck", required=True, help="Deck JSON to review.")
    review.add_argument("--collection", default=DEFAULT_COLLECTION_PATH, help="Enriched collection CSV.")
    review.add_argument("--output", default="", help="JSON tuning report output. Defaults to data/output/<deck>_tuning.json.")
    review.add_argument("--max-suggestions", type=int, default=10, help="Maximum number of swaps to suggest.")
    review.add_argument("--theme", default="", help="Optional theme hint to guide tuning.")
    review.add_argument("--compare-to", default="", help="Optional older deck JSON to compare against.")
    review.add_argument("--diff-output", default="", help="Optional JSON diff report output.")
    review.set_defaults(func=run_review)

    export = subparsers.add_parser("export", help="Export a deck to ManaBox CSV or plain text.")
    export.add_argument("--deck", required=True, help="Deck JSON to export.")
    export.add_argument("--format", choices=["manabox", "text"], default="manabox", help="Export format.")
    export.add_argument("--collection", default=DEFAULT_COLLECTION_PATH, help="Enriched collection CSV for ManaBox metadata.")
    export.add_argument("--output", default="", help="Output file. Defaults to data/output based on the deck name.")
    export.add_argument("--no-categories", action="store_true", help="For text export, write one flat list.")
    export.set_defaults(func=run_export)

    import_deck = subparsers.add_parser("import-deck", help="Import a ManaBox-style deck CSV into project deck JSON.")
    import_deck.add_argument("--input", required=True, help="ManaBox-style deck CSV.")
    import_deck.add_argument("--commander", required=True, help="Commander name.")
    import_deck.add_argument("--collection", default=DEFAULT_COLLECTION_PATH, help="Enriched collection CSV.")
    import_deck.add_argument("--output", required=True, help="Project deck JSON output.")
    import_deck.add_argument("--name", default="", help="Optional deck name.")
    import_deck.set_defaults(func=run_import_deck)

    privacy = subparsers.add_parser("privacy-check", help="Check whether private/output files are tracked by Git.")
    privacy.set_defaults(func=run_privacy_check)

    return parser.parse_args()


def run_scan(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    enriched_path = output_dir / "collection_enriched.csv"
    commanders_path = output_dir / "commander_candidates.csv"
    analysis_dir = output_dir / "analysis"

    print(f"Reading ManaBox export: {args.input}")
    collection_df = read_csv_file(args.input)
    ensure_columns(collection_df, REQUIRED_MANABOX_COLUMNS)

    unique_ids = normalize_scryfall_ids(collection_df["Scryfall ID"])
    print(f"Found {len(unique_ids)} unique Scryfall IDs")
    scryfall_lookup = fetch_scryfall_cards_by_ids(unique_ids, sleep_seconds=args.sleep_seconds)
    scryfall_rows = [{"Scryfall ID": scryfall_id, **metadata} for scryfall_id, metadata in scryfall_lookup.items()]
    scryfall_df = pd.DataFrame(scryfall_rows) if scryfall_rows else pd.DataFrame(columns=["Scryfall ID"])
    enriched_df = collection_df.merge(scryfall_df, on="Scryfall ID", how="left")
    enriched_df.to_csv(enriched_path, index=False)
    print(f"Saved enriched collection to: {enriched_path}")

    commander_df = write_commander_candidates(enriched_df, commanders_path)
    print(f"Found {len(commander_df)} commander candidates")
    print(f"Saved commander candidates to: {commanders_path}")

    if not args.skip_analysis:
        write_analysis_outputs(enriched_df, commander_df, analysis_dir)
        print(f"Saved collection summaries to: {analysis_dir}")

    print_next_steps(commanders_path)
    return 0


def run_commanders(args: argparse.Namespace) -> int:
    enriched_df = read_csv_file(args.collection)
    commander_df = write_commander_candidates(enriched_df, Path(args.output))
    print(f"Found {len(commander_df)} commander candidates")
    print(f"Saved commander candidates to: {args.output}")
    return 0


def run_build(args: argparse.Namespace) -> int:
    stem = args.name or slugify(args.commander)
    output_dir = Path(args.output_dir)
    manabox_output = str(output_dir / f"{stem}_manabox.csv") if args.manabox else ""
    build_args = argparse.Namespace(
        commander=args.commander,
        collection=args.collection,
        output_dir=args.output_dir,
        name=args.name,
        target_size=args.target_size,
        land_count=args.land_count,
        theme=args.theme,
        provider=args.provider,
        no_viewer=args.no_viewer,
        no_prompt=args.no_prompt,
        no_validate=args.no_validate,
        manabox_output=manabox_output,
    )
    exit_code = build_commander_deck(build_args)
    deck_path = output_dir / f"{stem}_deck.json"
    if args.text:
        text_path = output_dir / f"{stem}_decklist.txt"
        export_deck_to_text(str(deck_path), str(text_path))
        print(f"Saved plain text decklist to: {text_path}")
    if not args.no_viewer:
        print(f"Open this file in your browser: {output_dir / f'{stem}_deck.html'}")
    return exit_code


def run_review(args: argparse.Namespace) -> int:
    output_path = args.output or default_output_for_deck(args.deck, "_tuning.json")
    report = tune_deck(
        deck_path=args.deck,
        collection_path=args.collection,
        output_path=output_path,
        max_suggestions=args.max_suggestions,
        theme=args.theme,
    )
    print(format_tuning_report(report))
    print(f"Saved tuning report to: {output_path}")

    if args.compare_to:
        diff_output = args.diff_output or default_output_for_deck(args.deck, "_diff.json")
        diff_report = compare_decks(args.compare_to, args.deck)
        print("")
        print(format_diff_report(diff_report))
        write_diff_json(diff_report, diff_output)
        print(f"Saved diff report to: {diff_output}")
    return 0


def run_export(args: argparse.Namespace) -> int:
    output_path = args.output or default_export_output(args.deck, args.format)
    if args.format == "manabox":
        export_deck_to_manabox_csv(args.deck, output_path, collection_path=args.collection)
        print(f"Saved ManaBox-style CSV to: {output_path}")
    else:
        export_deck_to_text(args.deck, output_path, include_categories=not args.no_categories)
        print(f"Saved plain text decklist to: {output_path}")
    return 0


def run_import_deck(args: argparse.Namespace) -> int:
    import_manabox_deck_csv(
        input_path=args.input,
        output_path=args.output,
        commander_name=args.commander,
        collection_path=args.collection,
        deck_name=args.name,
    )
    print(f"Saved deck JSON to: {args.output}")
    return 0


def run_privacy_check(_: argparse.Namespace) -> int:
    result = subprocess.run(
        ["git", "ls-files", "data/private", "data/output"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Could not run git privacy check.")
        return result.returncode

    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    unsafe = [line for line in tracked if not line.endswith(".gitkeep")]
    if unsafe:
        print("Private/output files are tracked:")
        for path in unsafe:
            print(f"- {path}")
        return 1
    print("Privacy check passed. Only .gitkeep placeholders are tracked in data/private and data/output.")
    return 0


def write_commander_candidates(enriched_df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    commander_df = build_commander_candidate_table(enriched_df)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    commander_df.to_csv(output_path, index=False)
    return commander_df


def write_analysis_outputs(enriched_df: pd.DataFrame, commander_df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    color_df = build_color_distribution(enriched_df)
    type_df = build_type_distribution(enriched_df)
    summary = build_summary(enriched_df, commander_df)
    (output_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    color_df.to_csv(output_dir / "color_distribution.csv", index=False)
    type_df.to_csv(output_dir / "type_distribution.csv", index=False)
    commander_df.to_csv(output_dir / "candidate_commanders.csv", index=False)


def print_next_steps(commanders_path: Path) -> None:
    print("")
    print("Next steps:")
    print(f"1. Open {commanders_path} and pick a commander.")
    print('2. Build a deck with: mtg-collection build --commander "Commander Name"')


def default_output_for_deck(deck_path: str, suffix: str) -> str:
    path = Path(deck_path)
    return str(Path(DEFAULT_OUTPUT_DIR) / f"{path.stem}{suffix}")


def default_export_output(deck_path: str, export_format: str) -> str:
    suffix = "_manabox.csv" if export_format == "manabox" else "_decklist.txt"
    return default_output_for_deck(deck_path, suffix)


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
