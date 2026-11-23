"""Verify reachability, fragment destinations, offline assets and official membership."""
import json
import posixpath
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

DOC = Path(__file__).resolve().parents[1] / "docs"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = set()
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
            else:
                self.targets.add(url)


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

records = json.loads((DOC/"data"/"chars.json").read_text("utf-8"))
expected = {f"char/{ord(c):04x}.html" for c in records}
if len(expected) != 4808 or expected != {p for p in pages if p.startswith("char/")}:
    raise ValueError("Character page set does not match the official table")
print(f"OK: {len(seen)} reachable pages; all relative links, fragments and offline assets resolve.")
