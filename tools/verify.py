"""Verify reachability, fragment destinations, offline assets and official membership."""
import json
import posixpath
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlsplit

DOC = Path(__file__).resolve().parents[1] / "docs"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = set()
        self.external = set()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        url = attrs.get("href") or attrs.get("src")
        if url:
            if urlsplit(url).scheme or url.startswith("//"):
                if tag != "a":
                    raise ValueError(f"Online dependency: {url}")
                self.external.add(url)
            else:
                self.targets.add(url)


class GroupFilter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.checkboxes = []
        self.groups = {}
        self.div_depth = 0
        self.filter_depth = None
        self.list_depth = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.div_depth += 1
            if attrs.get("class") == "group-filter":
                self.filter_depth = self.div_depth
            elif attrs.get("class") == "group-list" and self.div_depth == self.filter_depth + 1:
                self.list_depth = self.div_depth
        elif tag == "input" and attrs.get("id") == "hide-singletons" and self.div_depth == self.filter_depth:
            self.checkboxes.append(attrs)
        elif tag == "details" and self.div_depth == self.list_depth:
            self.groups[attrs.get("id")] = "data-singleton" in attrs

    def handle_endtag(self, tag):
        if tag == "div":
            if self.div_depth == self.list_depth:
                self.list_depth = None
            if self.div_depth == self.filter_depth:
                self.filter_depth = None
            self.div_depth -= 1


files = {p.relative_to(DOC).as_posix() for p in DOC.rglob("*") if p.is_file()}
pages = {p for p in files if p.endswith(".html")}
anchors, edges, fragments = {}, defaultdict(set), []
for name in pages:
    parser = Links()
    parser.feed((DOC / name).read_text("utf-8"))
    anchors[name] = parser.ids
    for target in parser.targets:
        path, _, fragment = target.partition("#")
        dest = posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) if path else name
        if dest not in files:
            raise ValueError(f"Broken link in {name}: {target}")
        if dest in pages:
            edges[name].add(dest)
        if fragment:
            fragments.append((name,dest,fragment))
for name, dest, fragment in fragments:
    if fragment not in anchors[dest]:
        raise ValueError(f"{name}: missing {dest}#{fragment}")
todo = ["index.html"]
seen = set()
while todo:
    name = todo.pop()
    if name not in seen:
        seen.add(name)
        todo.extend(edges[name] - seen)
if seen != pages:
    raise ValueError(f"Orphan pages: {pages-seen}")

for name in ("radicals", "families", "phonetics", "semantics", "confusion"):
    group_filter = GroupFilter()
    group_filter.feed((DOC/f"{name}.html").read_text("utf-8"))
    groups = json.loads((DOC/"data"/f"{name}.json").read_text("utf-8"))
    if name == "confusion":
        expected_groups = {f'u{ord(group["chars"][0]):04x}': len(group["chars"]) == 1 for group in groups}
    else:
        expected_groups = {f"u{ord(part):04x}": len(members) == 1 for part, members in groups.items()}
    if (len(group_filter.checkboxes) != 1 or group_filter.checkboxes[0].get("type") != "checkbox" or
            "checked" in group_filter.checkboxes[0] or group_filter.groups != expected_groups):
        raise ValueError(f"{name}: singleton filter or group membership is incorrect")

records = json.loads((DOC/"data"/"chars.json").read_text("utf-8"))
expected = {f"char/{ord(c):04x}.html" for c in records}
if len(expected) != 4808 or expected != {p for p in pages if p.startswith("char/")}:
    raise ValueError("Character page set does not match the official table")
record = records.get("汩")
if not record or record["id"] != "A02149" or record["pdfCode"].lower() != "6c69":
    raise ValueError("A02149 must be 汩 (U+6C69)")
audit = json.loads((DOC/"data"/"audit.json").read_text("utf-8"))
exception = next((e for e in audit["exceptions"] if e["id"] == "A02149"), None)
if not exception or exception["selected"] != "汩" or exception["pdfGlyph"] != "汨":
    raise ValueError("A02149 text-extraction exception is not recorded correctly")
idiom_data = json.loads((DOC/"data"/"idioms.json").read_text("utf-8"))
if idiom_data["version"] != "2020_20260929" or len(idiom_data["records"]) != 5489:
    raise ValueError("MOE idiom data version or record count is incorrect")
sample = next((e for e in idiom_data["records"] if e["word"] == "花天酒地"), None)
if (not sample or sample["zhuyin"] != "ㄏㄨㄚ　ㄊㄧㄢ　ㄐㄧㄡˇ　ㄉㄧˋ" or
        sample["pinyin"] != "huā tiān jiǔ dì"):
    raise ValueError("MOE idiom title or pronunciation is not preserved")
if not (DOC/"data"/"idioms-usage.odt").is_file():
    raise ValueError("Complete MOE idiom usage instructions are missing")
flower_html = (DOC/"char"/"82b1.html").read_text("utf-8")
if any(value not in flower_html for value in (sample["word"], sample["zhuyin"], sample["pinyin"])):
    raise ValueError("MOE idiom title or pronunciation is missing from the character page")
variation = next(e for e in idiom_data["records"] if e["word"] == "曇花一現")
variation_html = flower_html
if ("ㄊㄢˊ　ㄏㄨㄚ　ㄧ　ㄒㄧㄢˋ<br>（變）　ㄊㄢˊ　ㄏㄨㄚ　ㄧˊ　ㄒㄧㄢˋ" not in variation_html or
        "tán huā yī xiàn<br>（變） tán huā yí xiàn" not in variation_html or
        "（變）" not in variation["zhuyin"]):
    raise ValueError("MOE variation readings must start on a second line")
sources_html = (DOC/"sources.html").read_text("utf-8")
if "2020_20260929" not in sources_html or "姓名標示－禁止改作 3.0 臺灣授權條款" not in sources_html:
    raise ValueError("MOE idiom attribution or license notice is missing")
char_page = Links()
char_page.feed((DOC/"char"/"82b1.html").read_text("utf-8"))
direct_url = "https://dict.idioms.moe.edu.tw/idiomView.jsp?ID=1173&q=1"
if direct_url not in char_page.external:
    raise ValueError("Verified MOE idiom direct link is missing")
fallback = next(e for e in idiom_data["records"] if "花" in e["word"] and
                e["word"] not in {"花天酒地", "花言巧語", "花枝招展", "花團錦簇",
                                  "天花亂墜", "心花怒放", "五花八門", "生花妙筆",
                                  "如花似玉", "拈花惹草"})
fallback_url = ("https://dict.idioms.moe.edu.tw/idiomList.jsp?idiom=" +
                quote(fallback["word"], safe="") + "&qMd=0&qTp=1")
if fallback_url not in char_page.external:
    raise ValueError("Unverified MOE idiom does not use the official search fallback")
appendix_url = "https://dict.idioms.moe.edu.tw/idiomList.jsp?idiom=%E8%8A%B1&qMd=0&qTp=2"
if appendix_url not in char_page.external:
    raise ValueError("MOE appendix online search link is missing")
print(f"OK: {len(seen)} reachable pages; all relative links, fragments and offline assets resolve.")
