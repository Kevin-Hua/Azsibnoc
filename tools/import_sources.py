"""Refresh the checked-in factual subset from a directory of pinned upstream files."""
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(sys.argv[1])
OUT = ROOT / "source"
OUT.mkdir(exist_ok=True)
HASHES = {
    "moe.pdf": "82ed3a55962ebbd0ec55d14f357c21660ac52c04f7c7d10a44b4cc1a5d346b96",
    "Properties.zip": "3d56ef14cc8099893245dac58fe4718d2fa64812b9159352a98a4588ad3efa5c",
    "MapingTables.zip": "4502fcf7b433d679dee51127298929543ec7f4aa99be93cd219df1552bc3d2bf",
    "Unihan.zip": "f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e",
    "ids.txt": "cc2a0a97e6a51ed6ebe59870ef2af66e83f3c3c27387d79b4441bb2d791d78b1",
}
for filename, expected in HASHES.items():
    if hashlib.sha256((RAW / filename).read_bytes()).hexdigest() != expected:
        raise ValueError(f"Unexpected source revision: {filename}")

rows = {}
exceptions = []
pattern = r"(\d{5})\s+(A\d{5})\s+([a-fA-F0-9]{4,6})\s+(\S)"
for page, pdfpage in enumerate(PdfReader(RAW / "moe.pdf").pages[1:], 2):
    for number, record, hexcode, glyph in re.findall(pattern, pdfpage.extract_text()):
        char = chr(int(hexcode, 16))
        if unicodedata.normalize("NFKC", glyph) != char:
            if (record, char, glyph) != ("A02149", "汩", "汨"):
                raise ValueError(f"Unreviewed glyph mismatch: {record}")
            exceptions.append({"id": record, "pdfCode": hexcode, "pdfGlyph": glyph,
                               "selected": glyph, "reason": "依原表常用字欄，保留碼位欄差異。"})
            char = glyph
        if number != f"{len(rows)+1:05}" or record != "A"+number or char in rows:
            raise ValueError(f"Non-unique or out-of-order official record: {number}")
        rows[char] = dict(id=record, page=page, pdfCode=hexcode, pdfGlyph=glyph,
                          readings=[], unihan={}, ids="")
if len(rows) != 4808:
    raise ValueError(f"Incomplete official list: {len(rows)}")


def table(archive, name):
    return [line.split("\t") for line in archive.read(name).decode("utf-8-sig").splitlines() if line]


with ZipFile(RAW / "MapingTables.zip") as maps, ZipFile(RAW / "Properties.zip") as props:
    cns = defaultdict(list)
    for key, value in table(maps, "Unicode/CNS2UNICODE_Unicode BMP.txt"):
        cns[chr(int(value, 16))].append(key)
    roman = {z: p for z, p, *_ in table(props, "CNS_pinyin_2.txt")}
    sounds = defaultdict(list)
    for key, z in table(props, "CNS_phonetic.txt"):
        sounds[key].append(z)
    radical = dict(table(props, "CNS_radical.txt"))
    names = {k: v[0] for k, v, *_ in table(props, "CNS_radical_word.txt")}
    strokes = dict(table(props, "CNS_stroke.txt"))
    for char, row in rows.items():
        key = min(cns[char], key=lambda k: tuple(int(x, base) for x, base in zip(k.split("-"), (10, 16))))
        row.update(cns=key, radical=names[radical[key]], strokes=int(strokes[key]),
                   readings=[[z, roman[z]] for z in dict.fromkeys(sounds[key])])

fields = {"kRSUnicode", "kTotalStrokes", "kMandarin", "kHanYu", "kSBGY", "kSimplifiedVariant",
          "kTraditionalVariant", "kZVariant"}
with ZipFile(RAW / "Unihan.zip") as archive:
    for name in archive.namelist():
        for line in archive.read(name).decode().splitlines():
            if line.startswith("U+"):
                code, field, value = line.split("\t")
                char = chr(int(code[2:], 16))
                if char in rows and field in fields:
                    rows[char]["unihan"][field] = value

for line in (RAW / "ids.txt").read_text("utf-8-sig").splitlines():
    if line.startswith("U+"):
        _, char, *descriptions = line.split("\t")
        if char in rows:
            for desc in descriptions:
                match = re.fullmatch(r"\^(.+)\$\(([^)]*)\)", desc)
                if match and "T" in re.sub(r"\[[^]]*\]", "", match[2]):
                    rows[char]["ids"] = match[1]
                    break

def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

save("base.json", rows)
save("audit.json", dict(count=len(rows), missingIds=[], duplicateIds=[], duplicateCharacters=[],
                        exceptions=exceptions, hashes=HASHES))
print(f"Imported {len(rows)} official records; {len(exceptions)} documented discrepancy.")
