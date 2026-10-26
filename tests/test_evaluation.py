import json
import tempfile
import unittest
from pathlib import Path

from datamate.evaluation import evaluate, match_table, metrics, normalize, rounded, score_answer
from datamate.io import ContractError, read_jsonl, validate_answer


def answer(kind, value=None, aliases=None):
    record = {"id": "q", "type": kind}
    if value is not None:
        record["answer"] = value
    if aliases is not None:
        record["alias"] = aliases
    return record


class EvaluationTests(unittest.TestCase):
    def test_normalize_nfc_case_punctuation_whitespace(self):
        self.assertEqual(normalize("  CA\u0300-PHÊ\tSỮA! "), "cà phê sữa")

    def test_diacritics_preserved(self):
        self.assertEqual(score_answer(answer("string", "ca phe"), answer("string", "cà phê")), -1)

    def test_scalar_alias(self):
        self.assertEqual(score_answer(answer("string", "sp-001"), answer("string", "Sữa", ["SP-001"])), 1)

    def test_no_substring_matching(self):
        self.assertEqual(score_answer(answer("string", "Sữa"), answer("string", "Sữa tươi")), -1)

    def test_number_exact_and_float_noise(self):
        self.assertEqual(score_answer(answer("number", 0.1 + 0.2), answer("number", 0.3)), 1)
        self.assertEqual(score_answer(answer("number", 48250001), answer("number", 48250000)), -1)
        self.assertEqual(score_answer(answer("number", 1.234), answer("number", 1.23)), -1)

    def test_large_number_has_no_relative_tolerance(self):
        self.assertEqual(score_answer(answer("number", 1000000000001), answer("number", 1000000000000)), -1)

    def test_wrong_type_has_no_partial_credit(self):
        self.assertEqual(score_answer(answer("number", 12.4), answer("percent", 12.4)), -1)

    def test_percent_rounding_and_sign(self):
        self.assertEqual(score_answer(answer("percent", 12.344), answer("percent", 12.34)), 1)
        self.assertEqual(score_answer(answer("percent", -12.345), answer("percent", -12.35)), 1)
        self.assertEqual(score_answer(answer("percent", 0.124), answer("percent", 12.4)), -1)
        self.assertEqual(score_answer(answer("percent", 12.35), answer("percent", -12.35)), -1)

    def test_half_up_is_explicit(self):
        self.assertEqual(str(rounded(2.5, 0)), "3")
        self.assertEqual(str(rounded(2.345)), "2.35")

    def test_large_percent_does_not_crash_scorer(self):
        self.assertEqual(score_answer(answer("percent", 1e200), answer("percent", 12.3)), -1)

    def test_date_exact_month_and_day(self):
        self.assertEqual(score_answer(answer("date", "2026-08"), answer("date", "2026-08")), 1)
        self.assertEqual(score_answer(answer("date", "2026-08-01"), answer("date", "2026-08")), -1)

    def test_boolean(self):
        self.assertEqual(score_answer(answer("boolean", False), answer("boolean", False)), 1)
        self.assertEqual(score_answer(answer("boolean", True), answer("boolean", False)), -1)

    def test_ordered_list_and_item_aliases(self):
        ref = answer("list", ["Cà phê", "Trà"], [["SP1"], ["SP2"]])
        self.assertEqual(score_answer(answer("list", ["SP1", "SP2"]), ref), 1)
        self.assertEqual(score_answer(answer("list", ["SP2", "SP1"]), ref), -1)
        self.assertEqual(score_answer(answer("list", ["SP1"]), ref), -1)

    def test_mixed_numeric_list(self):
        self.assertEqual(score_answer(answer("list", [3, 10]), answer("list", [3, 10])), 1)
        self.assertEqual(score_answer(answer("list", ["3", 10]), answer("list", [3, 10])), -1)

    def test_table_rows_unordered_columns_reordered_and_aliases(self):
        ref = answer("table", {"columns": ["khach_hang", "so_tien_no"], "rows": [["Chị Lan", 30], ["Anh Tú", 20]]}, [["KH1"], ["KH2"]])
        pred = answer("table", {"columns": ["Số-tiền-no", "KHÁCH HÀNG"], "rows": [[20, "KH2"], [30, "KH1"]]})
        # Diacritics differ in first column label -> all-column fallback by position -> mismatch.
        self.assertEqual(score_answer(pred, ref), -1)
        pred["answer"]["columns"] = ["SO TIEN NO", "KHACH HANG"]
        self.assertEqual(score_answer(pred, ref), 1)

    def test_table_column_position_fallback(self):
        ref = answer("table", {"columns": ["khach_hang", "so_tien_no"], "rows": [["Lan", 30]]})
        pred = answer("table", {"columns": ["Tên", "Nợ"], "rows": [["LAN", 30]]})
        self.assertEqual(score_answer(pred, ref), 1)

    def test_table_bipartite_not_greedy(self):
        ref = {"columns": ["name", "n"], "rows": [["A", 1], ["B", 1]]}
        pred = {"columns": ["name", "n"], "rows": [["X", 1], ["A", 1]]}
        self.assertTrue(match_table(pred, ref, [["X"], ["X"]]))

    def test_table_missing_extra_rows_and_cells(self):
        ref = answer("table", {"columns": ["name", "n"], "rows": [["A", 1]]})
        for rows in [[], [["A", 2]], [["A", 1], ["B", 1]]]:
            self.assertEqual(score_answer(answer("table", {"columns": ["name", "n"], "rows": rows}), ref), -1)

    def test_table_set_duplicate_policy(self):
        ref = answer("table", {"columns": ["name", "n"], "rows": [["A", 1]]})
        self.assertEqual(score_answer(answer("table", {"columns": ["name", "n"], "rows": [["A", 1], ["A", 1]]}), ref), 1)

    def test_unanswerable_and_abstain(self):
        ref = answer("unanswerable")
        self.assertEqual(score_answer(answer("unanswerable"), ref), 1)
        self.assertEqual(score_answer(answer("number", 0), ref), -1)
        self.assertEqual(score_answer(answer("unanswerable"), answer("number", 0)), -1)
        self.assertEqual(score_answer(answer("abstain"), ref), 0)
        self.assertEqual(score_answer(None, ref), 0)

    def test_pa_denominator_includes_missing(self):
        result = metrics([1, -1, 0, 1])
        self.assertEqual(result["PA"], 0.25)
        self.assertEqual(result["coverage"], 0.75)
        self.assertEqual(result["answered_accuracy"], 2 / 3)

    def test_empty_and_all_abstain(self):
        self.assertIsNone(metrics([])["PA"])
        self.assertIsNone(metrics([0])["answered_accuracy"])
        self.assertEqual(metrics([0])["PA"], 0)

    def test_dataset_slices(self):
        qs = [{"id": "q", "business_id": "b1"}, {"id": "r", "business_id": "b2"}]
        refs = [answer("number", 1), {"id": "r", "type": "number", "answer": 2}]
        result, rows = evaluate(qs, refs, [answer("number", 1)])
        self.assertEqual(result["PA"], 0.5)
        self.assertEqual(result["abstain"], 1)
        self.assertEqual(rows[1]["prediction_type"], "missing")
        self.assertEqual(result["slices"]["business"]["b2"]["PA"], 0)

    def test_dataset_unknown_duplicate_or_missing_reference_rejected(self):
        qs = [{"id": "q", "business_id": "b"}]
        ref = answer("number", 1)
        for refs, preds in [([], []), ([ref], [ref, ref]), ([ref], [{**ref, "id": "alien"}])]:
            with self.assertRaises(ContractError):
                evaluate(qs, refs, preds)


class ContractTests(unittest.TestCase):
    def test_malformed_answer_rejected(self):
        records = [answer("number", True), answer("number", "12"), answer("number", float("inf")),
                   answer("percent", float("nan")), answer("boolean", 1), answer("date", "2025-02-29"),
                   answer("date", "2026-13"), answer("list", [True]), answer("list", [{"x": 1}]),
                   answer("table", {"columns": ["x"], "rows": [[1, 2]]}),
                   {**answer("unanswerable"), "reason": 1}, answer("invented", 2)]
        for record in records:
            with self.subTest(record=record), self.assertRaises(ContractError):
                validate_answer(record)

    def test_jsonl_rejects_ambiguous_and_nonfinite_records(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            for text in ['{"id":"q","id":"r"}', '{"id":"q","answer":NaN}',
                         '{"id":"q"}\n{"id":"q"}', '{broken}', '[]', '{"id": 3}']:
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ContractError):
                    read_jsonl(path)

    def test_jsonl_bom_blank_lines_and_unicode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            path.write_text('\ufeff\n' + json.dumps({"id": "q", "type": "string", "answer": "Cà phê"}, ensure_ascii=False))
            self.assertEqual(read_jsonl(path)[0]["answer"], "Cà phê")


if __name__ == "__main__":
    unittest.main()
