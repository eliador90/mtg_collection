from __future__ import annotations

import argparse
from pathlib import Path

from deck_generation import summarize_result, write_ai_prompt, write_deck_json
from deck_providers import DeckDraftRequest, create_provider, provider_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a first-pass Commander deck draft from an enriched collection CSV."
    )
    parser.add_argument("--commander", required=True, help="Commander name to build around.")
    parser.add_argument("--collection", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument("--output", required=True, help="Path for the generated deck JSON.")
    parser.add_argument(
        "--target-size",
        type=int,
        default=100,
        help="Total deck size including the commander. Defaults to 100 for Commander.",
    )
    parser.add_argument(
        "--land-count",
        type=int,
        default=None,
        help="Number of lands to include. Defaults to a Commander-friendly 37 for 100-card decks.",
    )
    parser.add_argument(
        "--theme",
        default="",
        help="Optional plain-language theme hint, such as 'suspend big spells' or 'faerie tempo'.",
    )
    parser.add_argument(
        "--provider",
        default="local",
        choices=provider_names(),
        help="Deck draft provider. Only 'local' is implemented today; API providers are planned extension points.",
    )
    parser.add_argument(
        "--prompt-output",
        default="",
        help="Optional path for an AI-ready prompt file that can be pasted into Codex, ChatGPT, Claude, or Claude Code.",
    )
    parser.add_argument(
        "--viewer-output",
        default="",
        help="Optional path for an HTML viewer. If set, this also runs the existing deck viewer generator.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = create_provider(args.provider)
    request = DeckDraftRequest(
        collection_path=args.collection,
        commander_name=args.commander,
        target_size=args.target_size,
        land_count=args.land_count,
        theme=args.theme,
    )
    result = provider.draft_deck(request)

    write_deck_json(result.deck, args.output)
    print(summarize_result(result))
    print(f"Saved deck JSON to: {args.output}")

    if args.prompt_output:
        write_ai_prompt(result, args.prompt_output)
        print(f"Saved AI-ready prompt to: {args.prompt_output}")

    if args.viewer_output:
        from generate_deck_viewer import build_deck_cards, load_collection_lookup, render_html

        collection_lookup = load_collection_lookup(args.collection)
        deck_name, cards, refinement = build_deck_cards(args.output, collection_lookup)
        viewer_path = Path(args.viewer_output)
        viewer_path.parent.mkdir(parents=True, exist_ok=True)
        viewer_path.write_text(render_html(deck_name, cards, refinement), encoding="utf-8")
        print(f"Saved deck viewer to: {args.viewer_output}")


if __name__ == "__main__":
    main()
