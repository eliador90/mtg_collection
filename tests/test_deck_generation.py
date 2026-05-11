from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deck_generation import generate_local_deck_draft, write_ai_prompt, write_deck_json  # noqa: E402
from deck_diff import compare_decks  # noqa: E402
from deck_io import export_deck_to_manabox_csv, import_manabox_deck_csv  # noqa: E402
from deck_providers import DeckDraftRequest, create_provider, provider_names  # noqa: E402
from deck_text_export import export_deck_to_text  # noqa: E402
from deck_tuning import tune_deck  # noqa: E402
from deck_validation import attach_validation_report, validate_deck  # noqa: E402
from mtg_collection_cli import run_build, run_commanders, run_export  # noqa: E402


def deck_card_total(deck: dict) -> int:
    return 1 + sum(int(card.get("count", 1)) for card in deck["cards"])


class DeckGenerationSmokeTest(unittest.TestCase):
    def test_sample_deck_generation_reaches_target_size(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        self.assertEqual(result.deck["commander"]["name"], "Shorikai, Genesis Engine")
        self.assertEqual(deck_card_total(result.deck), 8)
        self.assertIn("generation", result.deck)
        self.assertIn("quality", result.deck["generation"])
        self.assertIn("quality_notes", result.deck["refinement"])

    def test_deck_and_prompt_can_be_written(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            prompt_path = Path(temp_dir) / "prompt.md"

            write_deck_json(result.deck, str(deck_path))
            write_ai_prompt(result, str(prompt_path))

            self.assertTrue(deck_path.exists())
            self.assertTrue(prompt_path.exists())
            self.assertIn("Shorikai, Genesis Engine", prompt_path.read_text(encoding="utf-8"))

    def test_generated_sample_deck_validates(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_json(result.deck, str(deck_path))

            report = validate_deck(
                deck_path=str(deck_path),
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                target_size=8,
                min_lands=1,
                max_lands=7,
            )

            self.assertTrue(report.ok, [issue.message for issue in report.errors])

    def test_validation_report_can_be_attached_to_deck(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_json(result.deck, str(deck_path))
            report = validate_deck(
                deck_path=str(deck_path),
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                target_size=8,
                min_lands=1,
                max_lands=7,
            )
            updated = attach_validation_report(result.deck, report)

            self.assertIn("validation_report", updated["refinement"])
            self.assertTrue(updated["refinement"]["validation_report"]["ok"])

    def test_validator_rejects_wrong_deck_size(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_json(result.deck, str(deck_path))

            report = validate_deck(
                deck_path=str(deck_path),
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                target_size=100,
            )

            self.assertFalse(report.ok)
            self.assertTrue(any(issue.code == "wrong_deck_size" for issue in report.errors))

    def test_local_provider_generates_deck(self) -> None:
        provider = create_provider("local")
        result = provider.draft_deck(
            DeckDraftRequest(
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                commander_name="Shorikai, Genesis Engine",
                target_size=8,
            )
        )

        self.assertEqual(result.deck["commander"]["name"], "Shorikai, Genesis Engine")
        self.assertIn("openai", provider_names())

    def test_manabox_export_and_import_round_trip(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            csv_path = Path(temp_dir) / "deck.csv"
            imported_path = Path(temp_dir) / "imported.json"

            write_deck_json(result.deck, str(deck_path))
            export_deck_to_manabox_csv(
                deck_path=str(deck_path),
                output_path=str(csv_path),
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            )
            import_manabox_deck_csv(
                input_path=str(csv_path),
                output_path=str(imported_path),
                commander_name="Shorikai, Genesis Engine",
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            )

            self.assertIn("Scryfall ID", csv_path.read_text(encoding="utf-8"))
            self.assertIn("Shorikai, Genesis Engine", imported_path.read_text(encoding="utf-8"))

    def test_plain_text_export(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            text_path = Path(temp_dir) / "deck.txt"
            write_deck_json(result.deck, str(deck_path))
            export_deck_to_text(str(deck_path), str(text_path))

            text = text_path.read_text(encoding="utf-8")
            self.assertIn("Commander", text)
            self.assertIn("1 Shorikai, Genesis Engine", text)

    def test_compare_decks_detects_changes(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )
        changed = dict(result.deck)
        changed["cards"] = result.deck["cards"][:-1]

        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = Path(temp_dir) / "old.json"
            new_path = Path(temp_dir) / "new.json"
            write_deck_json(result.deck, str(old_path))
            write_deck_json(changed, str(new_path))

            report = compare_decks(str(old_path), str(new_path))
            self.assertTrue(report.has_changes)
            self.assertTrue(report.removed)

    def test_tune_deck_returns_suggestions_key(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            report_path = Path(temp_dir) / "tuning.json"
            write_deck_json(result.deck, str(deck_path))
            report = tune_deck(
                deck_path=str(deck_path),
                collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                output_path=str(report_path),
                max_suggestions=3,
            )

            self.assertIn("suggestions", report)
            self.assertTrue(report["validation_ok"])
            self.assertTrue(report_path.exists())

    def test_beginner_cli_commanders_and_build_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            commanders_path = Path(temp_dir) / "commanders.csv"
            build_args = type(
                "Args",
                (),
                {
                    "commander": "Shorikai, Genesis Engine",
                    "collection": str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                    "output_dir": temp_dir,
                    "name": "beginner_sample",
                    "target_size": 8,
                    "land_count": None,
                    "theme": "",
                    "provider": "local",
                    "no_viewer": True,
                    "no_prompt": False,
                    "no_validate": False,
                    "manabox": True,
                    "text": True,
                },
            )()
            commander_args = type(
                "Args",
                (),
                {
                    "collection": str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                    "output": str(commanders_path),
                },
            )()

            self.assertEqual(run_commanders(commander_args), 0)
            self.assertTrue(commanders_path.exists())
            self.assertEqual(run_build(build_args), 0)
            self.assertTrue((Path(temp_dir) / "beginner_sample_deck.json").exists())
            self.assertTrue((Path(temp_dir) / "beginner_sample_ai_prompt.md").exists())
            self.assertTrue((Path(temp_dir) / "beginner_sample_manabox.csv").exists())
            self.assertTrue((Path(temp_dir) / "beginner_sample_decklist.txt").exists())

    def test_beginner_cli_export_workflow(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            output_path = Path(temp_dir) / "decklist.txt"
            write_deck_json(result.deck, str(deck_path))
            args = type(
                "Args",
                (),
                {
                    "deck": str(deck_path),
                    "format": "text",
                    "collection": str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                    "output": str(output_path),
                    "no_categories": False,
                },
            )()

            self.assertEqual(run_export(args), 0)
            self.assertIn("Shorikai, Genesis Engine", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
