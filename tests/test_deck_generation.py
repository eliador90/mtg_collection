from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deck_generation import generate_local_deck_draft, write_ai_prompt, write_deck_json  # noqa: E402
from deck_diff import compare_decks  # noqa: E402
from deck_io import export_deck_to_manabox_csv, import_manabox_deck_csv  # noqa: E402
from deck_providers import DeckDraftRequest, create_provider, parse_deck_json_response, provider_names  # noqa: E402
from deck_text_export import export_deck_to_text  # noqa: E402
from deck_tuning import attach_tuning_report, tune_deck  # noqa: E402
from deck_validation import attach_validation_report, validate_deck  # noqa: E402
from mtg_collection_cli import (  # noqa: E402
    default_export_output,
    default_output_for_deck,
    resolve_deck_path,
    run_build,
    run_commanders,
    run_export,
)


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

    def test_openai_provider_requires_api_key(self) -> None:
        provider = create_provider("openai")
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                provider.draft_deck(
                    DeckDraftRequest(
                        collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                        commander_name="Shorikai, Genesis Engine",
                        target_size=8,
                    )
                )

    def test_openai_json_response_parser_accepts_markdown_fence(self) -> None:
        deck = parse_deck_json_response(
            '```json\n{"name":"Test","commander":{"name":"Shorikai, Genesis Engine"},"cards":[]}\n```'
        )

        self.assertEqual(deck["name"], "Test")
        self.assertEqual(deck["commander"]["name"], "Shorikai, Genesis Engine")

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
                    "model": "",
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
            deck_dir = Path(temp_dir) / "beginner_sample"
            self.assertTrue((deck_dir / "beginner_sample_deck.json").exists())
            self.assertTrue((deck_dir / "beginner_sample_ai_prompt.md").exists())
            self.assertTrue((deck_dir / "beginner_sample_manabox.csv").exists())
            self.assertTrue((deck_dir / "beginner_sample_decklist.txt").exists())
            next_steps = deck_dir / "beginner_sample_next_steps.txt"
            self.assertTrue(next_steps.exists())
            self.assertIn("mtg-collection review --folder", next_steps.read_text(encoding="utf-8"))

    def test_output_folder_defaults_to_commander_and_theme(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_args = type(
                "Args",
                (),
                {
                    "commander": "Shorikai, Genesis Engine",
                    "collection": str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                    "output_dir": temp_dir,
                    "name": "",
                    "target_size": 8,
                    "land_count": None,
                    "theme": "artifact tokens",
                    "model": "",
                    "provider": "local",
                    "no_viewer": True,
                    "no_prompt": True,
                    "no_validate": False,
                    "manabox": False,
                    "text": False,
                },
            )()

            self.assertEqual(run_build(build_args), 0)
            deck_dir = Path(temp_dir) / "shorikai_genesis_engine_artifact_tokens"
            self.assertTrue((deck_dir / "shorikai_genesis_engine_artifact_tokens_deck.json").exists())

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
                    "folder": "",
                    "format": "text",
                    "collection": str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
                    "output": str(output_path),
                    "no_categories": False,
                },
            )()

            self.assertEqual(run_export(args), 0)
            self.assertIn("Shorikai, Genesis Engine", output_path.read_text(encoding="utf-8"))

    def test_default_related_outputs_use_deck_name(self) -> None:
        named_deck = str(Path("data/output/my_deck/my_deck_deck.json"))
        old_deck = str(Path("data/output/my_deck/deck.json"))

        self.assertEqual(
            default_output_for_deck(named_deck, "_tuning.json"),
            str(Path("data/output/my_deck/my_deck_tuning.json")),
        )
        self.assertEqual(
            default_export_output(named_deck, "manabox"),
            str(Path("data/output/my_deck/my_deck_manabox.csv")),
        )
        self.assertEqual(
            default_output_for_deck(old_deck, "_tuning.json"),
            str(Path("data/output/my_deck/my_deck_tuning.json")),
        )
        self.assertEqual(
            default_export_output(old_deck, "text"),
            str(Path("data/output/my_deck/my_deck_decklist.txt")),
        )

    def test_resolve_deck_path_accepts_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_dir = Path(temp_dir) / "my_deck"
            deck_dir.mkdir()
            deck_path = deck_dir / "my_deck_deck.json"
            deck_path.write_text("{}", encoding="utf-8")

            self.assertEqual(resolve_deck_path(folder=str(deck_dir)), str(deck_path))

    def test_tuning_report_can_be_attached_to_deck(self) -> None:
        result = generate_local_deck_draft(
            collection_path=str(PROJECT_ROOT / "data" / "sample" / "collection_enriched_sample.csv"),
            commander_name="Shorikai, Genesis Engine",
            target_size=8,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            deck_path = Path(temp_dir) / "deck.json"
            write_deck_json(result.deck, str(deck_path))
            updated = attach_tuning_report(
                str(deck_path),
                {
                    "validation_ok": True,
                    "validation_warnings": [],
                    "suggestions": [
                        {
                            "cut": "Sol Ring",
                            "add": "Arcane Signet",
                            "reason": "Test suggestion.",
                        }
                    ],
                },
            )

            self.assertIn("upgrade_suggestions", updated["refinement"])
            self.assertEqual(updated["refinement"]["upgrade_suggestions"][0]["add"], "Arcane Signet")


if __name__ == "__main__":
    unittest.main()
