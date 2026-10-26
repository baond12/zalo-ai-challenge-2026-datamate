import sqlite3
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from datamate.audit import column_role, parsed_date, profile_table, relationship_candidates
from datamate.contracts import load_split
from datamate.ingest import csv_rows, sqlite_readonly, xlsx_package, xlsx_rows
from datamate.io import ContractError, write_jsonl


class ReadersTests(unittest.TestCase):
    def test_csv_semicolon_bom_and_quoted_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            path.write_text('\ufeffMã;Tên;SL\nD1;"Cà\nphê";2\n', encoding="utf-8")
            rows = list(csv_rows(path))
            self.assertEqual(rows[1][1], ["D1", "Cà\nphê", "2"])

    def test_sqlite_is_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.sqlite"
            with sqlite3.connect(path) as con:
                con.execute('CREATE TABLE t (id TEXT)')
                con.execute("INSERT INTO t VALUES ('A')")
            with sqlite_readonly(path) as con:
                self.assertEqual(con.execute("SELECT * FROM t").fetchone(), ("A",))
                with self.assertRaises(sqlite3.OperationalError):
                    con.execute("DELETE FROM t")

    def test_xlsx_sparse_shared_inline_formula_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.xlsx"
            with ZipFile(path, "w") as z:
                z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="1"/><sheets><sheet name="2025" sheetId="1" r:id="rId1"/></sheets></workbook>')
                z.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId1" Target="/xl/worksheets/sheet1.xml"/></Relationships>')
                z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><r><t>Cà</t></r><r><t> phê</t></r></si></sst>')
                z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>SL</t></is></c></row><row r="3"><c r="A3" t="b"><v>1</v></c><c r="C3" s="1"><f>1+2</f><v>3</v></c></row></sheetData><mergeCells><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
            with xlsx_package(path) as (z, strings, meta):
                structure = {}
                rows = list(xlsx_rows(z, strings, meta["sheets"][0]["member"], structure))
                self.assertEqual(rows[0][1], ["Cà phê", None, "SL"])
                self.assertEqual(rows[1], (3, [True, None, 3], 1, {2: 1}))
                self.assertEqual(structure["merged_ranges"], ["A1:B1"])
                self.assertTrue(meta["date1904"])

    def test_profile_observes_no_fill_or_dedup(self):
        rows = [(1, ["Mã đơn", "Ngày", "SL"], 0, {}),
                (2, ["D1", "01/01/2026", 2], 0, {}),
                (3, [None, "02/01/2026", -1], 0, {}),
                (4, ["D1", "01/01/2026", 2], 0, {})]
        table, keys = profile_table(iter(rows), Path("fixture.csv"), "csv", "## Cột trong `fixture.csv`\n- **Mã đơn**: mã đơn")
        self.assertEqual(table["rows"], 3)
        self.assertEqual(table["raw_duplicate_rows"], 1)
        self.assertEqual(table["columns"][0]["nulls"], 1)
        self.assertEqual(table["columns"][1]["date_min"], "2026-01-01")
        self.assertEqual(table["columns"][2]["negative_count"], 1)
        self.assertEqual(keys[0]["counts"]["D1"], 2)

    def test_date_locale_sheet_year_and_serial(self):
        self.assertEqual(parsed_date("02/03/2026", ""), "2026-03-02")
        self.assertEqual(parsed_date("29/02", "Thang02_2024"), "2024-02-29")
        self.assertIsNone(parsed_date("29/02/2025", ""))
        self.assertIsNone(parsed_date("01/02", "Sheet1"))
        self.assertEqual(parsed_date(1, "", True, True), "1904-01-02")
        self.assertEqual(parsed_date("1 thg 6 2025", ""), "2025-06-01")
        self.assertEqual(parsed_date(45717, ""), "2025-03-01")
        self.assertEqual(parsed_date("45658", ""), "2025-01-01")

    def test_quantity_conversion_and_duration_not_unit_or_date(self):
        self.assertEqual(column_role("SL quy đổi", ["số lượng đã đổi ra đơn vị cơ bản"])[0], "quantity_candidate")
        self.assertEqual(column_role("Hệ số", ["hệ số: số đơn vị cơ bản trong 1 đơn vị lớn"])[0], "conversion_factor_candidate")
        self.assertEqual(column_role("Số ngày được nợ", [])[0], "duration_candidate")
        self.assertEqual(column_role("Hạn nợ (ngày)", ["số ngày được nợ"])[0], "duration_candidate")

    def test_relationship_measures_orphans_and_multiplicity(self):
        keys = [{"path": "p", "table": "p", "column": "id", "role": "order_id", "counts": {"A": 1, "B": 1}},
                {"path": "c", "table": "c", "column": "id", "role": "order_id", "counts": {"A": 2, "X": 1}}]
        relation = relationship_candidates(keys)[0]
        self.assertEqual(relation["child_unmatched_distinct"], 1)
        self.assertEqual(relation["child_max_multiplicity"], 2)
        self.assertEqual(relation["child_matched_rows"], 2)


class RuntimeContextTests(unittest.TestCase):
    def make_split(self, root):
        (root / "rulebook.md").write_text("bán chạy = số lượng")
        (root / "calendar.csv").write_text("date,lunar_day\n2026-01-01,13\n")
        write_jsonl(root / "questions.jsonl", [{"id": "q", "business_id": "new", "question": "bao nhiêu", "as_of_date": "2026-01-01"}])
        directory = root / "data/new"
        directory.mkdir(parents=True)
        (directory / "README.md").write_text("doanh nghiệp mới")
        (directory / "raw.csv").write_text("a,b\n1,2\n")

    def test_context_reads_runtime_rulebook_not_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_split(root)
            (root / "answers.jsonl").write_text("not JSON; must not be read")
            first = load_split(root)
            (root / "rulebook.md").write_text("bán chạy = doanh thu")
            second = load_split(root)
            self.assertNotEqual(first.rulebook_sha256, second.rulebook_sha256)
            self.assertEqual(second.rulebook, "bán chạy = doanh thu")
            self.assertEqual(first.business("new").readme, "doanh nghiệp mới")

    def test_missing_rulebook_fails_instead_of_train_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_split(root)
            (root / "rulebook.md").unlink()
            with self.assertRaises(ContractError):
                load_split(root)

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_split(root)
            with self.assertRaises(ContractError):
                load_split(root).business("../../outside")


if __name__ == "__main__":
    unittest.main()
