"""Offline regression checks: frozen outcomes, cost erratum, and human packet."""
import csv
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
import zipfile

import reproduce


class ReproductionTests(unittest.TestCase):
    def test_benchmark_rebuild_matches_without_network_or_review_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "rebuilt"
            result = reproduce.rebuild_benchmark(destination)
            self.assertFalse(result["models_called"])
            self.assertEqual(reproduce.read(destination / "manifest.json")["human_review_status"], "pending")
            for original in (reproduce.DATA / "raw").rglob("*.txt"):
                self.assertEqual(original.read_bytes(), (destination / original.relative_to(reproduce.DATA)).read_bytes())

    def test_replay_preserves_all_frozen_scores_and_costs(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "replay"
            with redirect_stdout(io.StringIO()):
                result = reproduce.replay(destination)
            self.assertEqual(result["replay"], "passed")
            self.assertEqual(result["subsets"]["normally_answerable"]["C_verified"]["correct"], 31)
            before = (destination / "test_results.json").read_bytes()
            reproduce.correct_costs(destination)
            self.assertEqual(before, (destination / "test_results.json").read_bytes())
            self.assertEqual(reproduce.sha(destination / "test_C_verified.jsonl"), reproduce.sha(reproduce.FROZEN / "test_C_verified.jsonl"))
            with self.assertRaisesRegex(ValueError, "NEW output"):
                reproduce.replay(destination)

    def test_reviewer_zip_has_blank_grades_and_no_answer_key(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "audit"
            reproduce.human_packet(destination)
            selection = reproduce.read(destination / "organizer_only/selection_receipt.json")
            self.assertEqual(selection["families"], 18)
            self.assertEqual(list(selection["by_category"].values()), [5] * 6)
            with zipfile.ZipFile(destination / "Reviewer_Packet.zip") as archive:
                names = archive.namelist()
                self.assertEqual(sum(n.startswith("sources/") for n in names), 72)
                self.assertFalse(any("organizer" in n or "answer_key" in n or "gold" in n for n in names))
                grades = list(csv.DictReader(io.StringIO(archive.read("grades.csv").decode("utf-8-sig"))))
                self.assertEqual(len(grades), 90)
                self.assertTrue(all(not r["correctness"] and not r["reviewer_id"] for r in grades))


if __name__ == "__main__":
    unittest.main()
