import json
import unittest
from pathlib import Path

from datamate.io import read_jsonl, sha256

ROOT = Path(__file__).resolve().parents[1]


class RegisterTests(unittest.TestCase):
    def test_documentary_requirements_have_live_sources(self):
        register = json.loads((ROOT / "docs/requirements.json").read_text())
        self.assertGreaterEqual(len(register["requirements"]), 30)
        for record in register["requirements"]:
            with self.subTest(id=record["id"]):
                self.assertEqual(sha256(ROOT / record["source"]), record["source_sha256"])
                for field in ("requirement", "section", "target_module", "verification", "implementation_status", "certainty"):
                    self.assertTrue(record[field])

    def test_every_rulebook_table_row_trace_is_current(self):
        register = json.loads((ROOT / "docs/RULE_REGISTER.json").read_text())
        ids = [r["id"] for r in register["rules"]]
        self.assertEqual(len(ids), len(set(ids)))
        for record in register["rules"]:
            source = ROOT / record["source"]
            self.assertEqual(sha256(source), record["source_sha256"])
            line = source.read_text().splitlines()[record["source_line"] - 1]
            if record["term"] != "paragraph":
                self.assertIn(record["term"], line)
                self.assertIn(record["requirement"].split(" | ")[0], line)


class SplitTests(unittest.TestCase):
    def setUp(self):
        lock_path = ROOT / "splits/LOCK.json"
        self.path = ROOT / json.loads(lock_path.read_text())["manifest"] if lock_path.exists() else ROOT / "splits/business_v1.json"
        if not self.path.exists():
            self.skipTest("Split generation not completed yet")
        self.split = json.loads(self.path.read_text())

    def test_split_lock_and_source_hashes(self):
        lock = json.loads((ROOT / "splits/LOCK.json").read_text())
        self.assertEqual(lock["sha256"], sha256(self.path))
        for name in ("questions", "answers"):
            self.assertEqual(self.split["provenance"][name + "_sha256"], sha256(ROOT / f"train/{name}.jsonl"))

    def test_business_partitions_and_cv_are_disjoint(self):
        all_ids = {p.name for p in (ROOT / "train/data").iterdir() if p.is_dir()}
        dev, holdout = set(self.split["development_businesses"]), set(self.split["holdout_businesses"])
        self.assertFalse(dev & holdout)
        self.assertEqual(dev | holdout, all_ids)
        val_seen = []
        for fold in self.split["folds"]:
            train, val = set(fold["training_businesses"]), set(fold["validation_businesses"])
            self.assertFalse(train & val)
            self.assertEqual(train | val, dev)
            self.assertFalse((train | val) & holdout)
            val_seen.extend(val)
        self.assertEqual(set(val_seen), dev)
        self.assertEqual(len(val_seen), len(dev))

    def test_schema_leakage_groups_never_cross_partitions_or_folds(self):
        holdout = set(self.split["holdout_businesses"])
        for group in self.split["leakage_groups"]:
            members = set(group)
            if members & holdout:
                self.assertTrue(members <= holdout)
            else:
                self.assertEqual(sum(members <= set(f["validation_businesses"]) for f in self.split["folds"]), 1)

    def test_question_assignments_are_complete_and_aligned(self):
        version = self.split["version"].removeprefix("business_")
        assignments = read_jsonl(ROOT / f"splits/question_assignments_{version}.jsonl")
        questions = read_jsonl(ROOT / "train/questions.jsonl")
        self.assertEqual({q["id"] for q in assignments}, {q["id"] for q in questions})
        mapping = {q["id"]: q for q in assignments}
        for q in questions:
            row = mapping[q["id"]]
            self.assertEqual(row["business_id"], q["business_id"])
            self.assertEqual(row["partition"] == "holdout", q["business_id"] in self.split["holdout_businesses"])

    def test_sector_holdout_excludes_industry_and_linked_schemas(self):
        taxonomy = json.loads((ROOT / "docs/BUSINESS_TAXONOMY.json").read_text())
        sectors = {r["business_id"]: r["sector_annotation"] for r in taxonomy["businesses"]}
        for fold in self.split["leave_one_sector_out"]:
            self.assertTrue(all(sectors[b] == fold["sector"] for b in fold["validation_businesses"]))
            self.assertTrue(all(sectors[b] != fold["sector"] for b in fold["training_businesses"]))
            self.assertTrue(all(sectors[b] != "unknown" for b in fold["training_businesses"]))
            blocked = set(fold["validation_businesses"] + fold["schema_linked_excluded_businesses"])
            for group in self.split["leakage_groups"]:
                if set(group) & set(fold["validation_businesses"]):
                    self.assertFalse(set(group) & set(fold["training_businesses"]))

    def test_grocery_tobacco_not_misclassified_as_pharmacy(self):
        taxonomy = json.loads((ROOT / "docs/BUSINESS_TAXONOMY.json").read_text())
        sectors = {r["business_id"]: r["sector_annotation"] for r in taxonomy["businesses"]}
        for business in ("biz_101", "biz_107", "biz_108"):
            self.assertEqual(sectors[business], "grocery")
        self.assertEqual(sectors["biz_110"], "unknown")


if __name__ == "__main__":
    unittest.main()
