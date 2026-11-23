"""Import the unchanged title and reading fields from the pinned MOE workbook."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "idioms.xlsx"
OUTPUT = ROOT / "source" / "idioms.json"
EXPECTED_SHA256 = "fa4395e9a94288b1f21266d3a5121b6c4d6709f22edb8e0f99bdf04df8d26f83"
VERSION = "2020_20260929"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise ValueError(f"Unexpected MOE idiom workbook: {SOURCE.name}")


def column(reference):
    letters = re.match(r"[A-Z]+", reference).group()
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - ord("A") + 1
    return value - 1


with ZipFile(SOURCE) as workbook:
    shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    shared = [
        "".join(node.text or "" for node in item.iter(f"{{{NS['x']}}}t"))
        for item in shared_root.findall("x:si", NS)
    ]
    sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))


def cell_value(cell):
    if cell.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{NS['x']}}}t"))
    value = cell.find("x:v", NS)
    if value is None:
        return ""
    return shared[int(value.text)] if cell.get("t") == "s" else value.text or ""


rows = sheet.findall(".//x:sheetData/x:row", NS)
if not rows:
    raise ValueError("MOE idiom workbook has no worksheet rows")

headers = {
    cell_value(cell): column(cell.get("r"))
    for cell in rows[0].findall("x:c", NS)
}
required = {
    "編號": "sourceId",
    "成語": "word",
    "注音": "zhuyin",
    "漢語拼音": "pinyin",
    "主條成語／非主條成語": "category",
}
if any(name not in headers for name in required):
    raise ValueError("MOE idiom workbook is missing expected columns")

records = []
seen_ids = set()
seen_words = set()
for row in rows[1:]:
    values = {column(cell.get("r")): cell_value(cell) for cell in row.findall("x:c", NS)}
    record = {
        target: values.get(headers[source], "")
        for source, target in required.items()
    }
    if not record["word"]:
        continue
    if not record["sourceId"] or record["sourceId"] in seen_ids:
        raise ValueError(f"Missing or duplicate MOE idiom source ID: {record['sourceId']}")
    if record["word"] in seen_words:
        raise ValueError(f"Duplicate MOE idiom title: {record['word']}")
    if not record["zhuyin"] or not record["pinyin"]:
        raise ValueError(f"Missing MOE pronunciation: {record['word']}")
    if record["category"] not in ("主條成語", "非主條成語"):
        raise ValueError(f"Unexpected MOE idiom category: {record['category']}")
    seen_ids.add(record["sourceId"])
    seen_words.add(record["word"])
    records.append(record)

if len(records) != 5489:
    raise ValueError(f"Expected 5489 MOE main-text idioms, found {len(records)}")

OUTPUT.write_text(json.dumps({
    "version": VERSION,
    "source": "https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/dict_idiomsdict_download.html",
    "sha256": EXPECTED_SHA256,
    "records": records,
}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"Imported {len(records)} unchanged MOE idiom records.")
