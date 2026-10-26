"""Read-only raw table streams, without semantic filling, dedup or normalization.

XLSX reader is deliberately an audit reader: cached formula values only, dates
stay raw numeric Excel serials and style IDs are exposed. Not an Excel engine.
"""

from __future__ import annotations

import csv
import posixpath
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from zipfile import ZipFile

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _tag(name):
    return f"{{{MAIN}}}{name}"


def _column_index(address):
    value = 0
    for char in address:
        if not char.isalpha():
            break
        value = value * 26 + ord(char.upper()) - ord("A") + 1
    return value - 1


@contextmanager
def xlsx_package(path: Path):
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            with archive.open("xl/sharedStrings.xml") as f:
                for _, node in ET.iterparse(f, events=("end",)):
                    if node.tag == _tag("si"):
                        strings.append("".join(t.text or "" for t in node.iter(_tag("t"))))
                        node.clear()
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        links = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in links}
        sheets = []
        for node in workbook.find(_tag("sheets")):
            target = targets[node.attrib[f"{{{REL}}}id"]]
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            sheets.append({"name": node.attrib["name"], "member": member, "state": node.attrib.get("state", "visible")})
        props = workbook.find(_tag("workbookPr"))
        metadata = {"date1904": props is not None and props.attrib.get("date1904") in ("1", "true"), "sheets": sheets}
        if "xl/styles.xml" in archive.namelist():
            styles = ET.fromstring(archive.read("xl/styles.xml"))
            metadata["custom_number_formats"] = [dict(n.attrib) for n in styles.findall(f"{_tag('numFmts')}/{_tag('numFmt')}")]
            metadata["cell_formats"] = [dict(n.attrib) for n in styles.findall(f"{_tag('cellXfs')}/{_tag('xf')}")]
        yield archive, strings, metadata


def xlsx_rows(archive, strings, member, structure=None):
    """Yield (Excel row number, values, formula count, cell styles)."""
    with archive.open(member) as f:
        root = None
        for event, node in ET.iterparse(f, events=("start", "end")):
            if root is None:
                root = node
            if event != "end":
                continue
            if node.tag == _tag("row"):
                values, styles, formulas = [], {}, 0
                for fallback, cell in enumerate(node.findall(_tag("c"))):
                    index = _column_index(cell.attrib["r"]) if "r" in cell.attrib else fallback
                    while len(values) <= index:
                        values.append(None)
                    kind = cell.attrib.get("t", "n")
                    v = cell.find(_tag("v"))
                    value = v.text if v is not None else None
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(_tag("t")))
                    elif kind == "s" and value is not None:
                        value = strings[int(value)]
                    elif kind == "b" and value is not None:
                        value = value == "1"
                    elif kind == "n" and value is not None:
                        try:
                            value = float(value) if any(c in value.lower() for c in (".", "e")) else int(value)
                        except ValueError:
                            pass
                    if "s" in cell.attrib:
                        styles[index] = int(cell.attrib["s"])
                    formulas += cell.find(_tag("f")) is not None
                    values[index] = value
                yield int(node.attrib.get("r", 0)), values, formulas, styles
                node.clear()
                # Remove accumulated row nodes from sheetData to bound memory.
                sheet_data = root.find(_tag("sheetData"))
                if sheet_data is not None:
                    sheet_data.clear()
            elif node.tag == _tag("mergeCell") and structure is not None:
                structure.setdefault("merged_ranges", []).append(node.attrib["ref"])


def csv_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(65536)
        stream.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        for i, row in enumerate(csv.reader(stream, dialect), 1):
            yield i, row, 0, {}


@contextmanager
def sqlite_readonly(path: Path):
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        yield con
    finally:
        con.close()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
