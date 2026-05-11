from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from deck_generation import summarize_result, write_ai_prompt, write_deck_json
from deck_io import export_deck_to_manabox_csv
from deck_providers import DeckDraftRequest, create_provider, provider_names
from deck_validation import attach_validation_report, format_report, validate_deck
from generate_deck_viewer import build_deck_cards, load_collection_lookup, render_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local Commander deck draft, validate it, and render an HTML viewer in one command."
    )
    parser.add_argument("--commander", required=True, help="Commander name to build around.")
    parser.add_argument("--collection", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument(
        "--output-dir",
        default="data/output",
        help="Directory for generated files. Defaults to data/output.",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Optional output folder name. Defaults to commander plus theme.",
    )
    parser.add_argument("--target-size", type=int, default=100, help="Deck size including commander. Defaults to 100.")
    parser.add_argument("--land-count", type=int, default=None, help="Optional exact land count.")
    parser.add_argument("--theme", default="", help="Optional theme hint, such as 'suspend big spells'.")
    parser.add_argument("--model", default="", help="Optional API model name. Only used by API providers such as openai.")
    parser.add_argument(
        "--provider",
        default="local",
        choices=provider_names(),
        help="Deck draft provider. Defaults to local. OpenAI is optional and requires OPENAI_API_KEY.",
    )
    parser.add_argument("--no-viewer", action="store_true", help="Skip HTML viewer generation.")
    parser.add_argument("--no-prompt", action="store_true", help="Skip AI-ready prompt generation.")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation after generation.")
    parser.add_argument(
        "--manabox-output",
        default="",
        help="Optional path for a ManaBox-style CSV export of the generated deck.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return build_commander_deck(args)


def build_commander_deck(args: argparse.Namespace) -> int:
    deck_dir = build_output_folder(args.output_dir, args.commander, args.theme, args.name)
    deck_dir.mkdir(parents=True, exist_ok=True)
    stem = deck_dir.name

    deck_path = deck_dir / f"{stem}_deck.json"
    viewer_path = deck_dir / f"{stem}_deck.html"
    prompt_path = deck_dir / f"{stem}_ai_prompt.md"
    validation_path = deck_dir / f"{stem}_validation.txt"
    next_steps_path = deck_dir / f"{stem}_next_steps.txt"

    provider = create_provider(args.provider)
    request = DeckDraftRequest(
        collection_path=args.collection,
        commander_name=args.commander,
        target_size=args.target_size,
        land_count=args.land_count,
        theme=args.theme,
        model=args.model,
    )
    result = provider.draft_deck(request)

    write_deck_json(result.deck, str(deck_path))
    print(summarize_result(result))
    print(f"Saved deck JSON to: {deck_path}")

    report = None
    formatted_report = ""
    if not args.no_validate:
        min_lands = 33 if args.target_size >= 90 else 1
        max_lands = 42 if args.target_size >= 90 else args.target_size - 1
        report = validate_deck(
            deck_path=str(deck_path),
            collection_path=args.collection,
            target_size=args.target_size,
            min_lands=min_lands,
            max_lands=max_lands,
        )
        result.deck = attach_validation_report(result.deck, report)
        write_deck_json(result.deck, str(deck_path))
        formatted_report = format_report(report)
        validation_path.write_text(formatted_report + "\n", encoding="utf-8")

    if not args.no_prompt:
        write_ai_prompt(result, str(prompt_path), collection_path=args.collection)
        print(f"Saved AI-ready prompt to: {prompt_path}")

    if not args.no_viewer:
        collection_lookup = load_collection_lookup(args.collection)
        deck_name, cards, refinement = build_deck_cards(str(deck_path), collection_lookup)
        viewer_path.write_text(render_html(deck_name, cards, refinement), encoding="utf-8")
        print(f"Saved deck viewer to: {viewer_path}")

    if args.manabox_output:
        export_deck_to_manabox_csv(str(deck_path), args.manabox_output, collection_path=args.collection)
        print(f"Saved ManaBox-style CSV to: {args.manabox_output}")

    write_next_steps_file(
        next_steps_path=next_steps_path,
        deck_dir=deck_dir,
        deck_path=deck_path,
        viewer_path=viewer_path if not args.no_viewer else None,
        prompt_path=prompt_path if not args.no_prompt else None,
        collection_path=args.collection,
        theme=args.theme,
    )
    print(f"Saved next steps to: {next_steps_path}")

    if args.no_validate:
        return 0
    print(formatted_report)
    print(f"Saved validation report to: {validation_path}")
    return 0 if report.ok else 1


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "commander_deck"


def build_output_stem(commander: str, theme: str = "", name: str = "") -> str:
    if name:
        return slugify(name)
    parts = [commander]
    if theme:
        parts.append(theme)
    return slugify(" ".join(parts))


def build_output_folder(output_dir: str, commander: str, theme: str = "", name: str = "") -> Path:
    return Path(output_dir) / build_output_stem(commander, theme, name)


def write_next_steps_file(
    next_steps_path: Path,
    deck_dir: Path,
    deck_path: Path,
    viewer_path: Path | None,
    prompt_path: Path | None,
    collection_path: str,
    theme: str = "",
) -> None:
    theme_part = f' --theme "{theme}"' if theme else ""
    lines = [
        "Next steps for this deck",
        "",
        "Use the deck JSON for commands:",
        str(deck_path),
        "",
        "Find replacement or upgrade ideas from your collection:",
        f'mtg-collection review --folder "{deck_dir}" --collection "{collection_path}"{theme_part}',
        "",
        "Export to ManaBox:",
        f'mtg-collection export --folder "{deck_dir}" --collection "{collection_path}" --format manabox',
        "",
        "Export to plain text:",
        f'mtg-collection export --folder "{deck_dir}" --format text',
        "",
        "File guide:",
        "- *_deck.json is the working deck file for commands.",
        "- *_deck.html is the browser viewer.",
        "- *_ai_prompt.md is the prompt for Codex, Claude Code, ChatGPT, Claude, or another assistant.",
        "- *_tuning.json is created by review and stores suggested swaps.",
        "- *_next_steps.txt is this command reminder.",
    ]
    if viewer_path is not None:
        lines[2:2] = ["Open the viewer in your browser:", str(viewer_path), ""]
    if prompt_path is not None:
        insert_at = lines.index("File guide:")
        lines[insert_at:insert_at] = ["Manual AI refinement prompt:", str(prompt_path), ""]
    next_steps_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
