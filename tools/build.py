"""Build the offline site using only Python's standard library."""
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs"
SRC = ROOT / "source"
VERSION = "0.2.2"
TITLE = "漢字部件字族百科"
OPS = dict(zip("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿼⿽⿾⿿㇯",
               "左右 上下 左中右 上中下 全包圍 上三包圍 下三包圍 左三包圍 左上包圍 右上包圍 左下包圍 交疊 右三包圍 右下包圍 鏡映 旋轉 減筆".split()))
NAV = {"radicals":"部首", "families":"部件字族", "phonetics":"聲旁", "semantics":"形旁",
       "confusion":"易混淆字群", "sources":"資料說明"}
UNKNOWN = "待考"


def load(file):
    return json.loads((SRC / file).read_text("utf-8"))


def write(name, text):
    path = DOC / name
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(text, encoding="utf-8")


def packed(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def dump(name, obj):
    write("data/" + name + ".json", packed(obj))


def code(c):
    return f"{ord(c):04x}"


def link(url, text):
    return f'<a href="{escape(url, quote=True)}">{escape(text)}</a>'


def tiles(chars, prefix=""):
    return '<div class="tiles">' + "".join(link(f"{prefix}char/{code(c)}.html", c) for c in chars) + "</div>"


def family(c, prefix=""):
    return link(f"{prefix}family/{code(c)}.html", c + "字族")


def group_filter(content):
    return ('<div class="group-filter"><input type="checkbox" id="hide-singletons">'
            '<label for="hide-singletons">隱藏只有 1 字的字群</label>'
            f'<div class="group-list">{content}</div></div>')


def page(path, title, body):
    prefix = "../" * path.count("/")
    nav = " ".join(link(prefix + k + ".html", v) for k, v in NAV.items())
    write(path, f'''<!doctype html>
<html lang="zh-Hant-TW"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · {TITLE}</title><link rel="stylesheet" href="{prefix}assets/app.css">
<header><a class="brand" href="{prefix}index.html">{TITLE}</a><nav aria-label="索引">{nav}</nav></header>
<main><h1>{escape(title)}</h1>{body}</main><footer>Azsibnoc · v{VERSION} · 可離線瀏覽</footer></html>''')


def decomposition(ids, char):
    tokens = iter(re.findall(r"\{\d+\}|.", ids.replace("〾", "")))
    parts = {}

    def parse(depth=0, removed=False):
        token = next(tokens)
        if token in OPS:
            count = 3 if token in "⿲⿳" else 1 if token in "⿾⿿" else 2
            for i in range(count):
                parse(depth+1, removed or (token == "㇯" and i == 1))
        elif depth and not removed and len(token) == 1 and token not in ("？", char):
            parts[token] = min(depth, parts.get(token, depth))
        return token

    first = parse()
    if next(tokens, None) is not None:
        raise ValueError(f"Invalid IDS: {char} {ids}")
    return OPS.get(first, "未再拆分"), parts


rows = load("base.json")
ed = load("editorial.json")
audit = load("audit.json")
idiom_data = load("idioms.json")
direct_links = load("idiom-direct-links.json")["entries"]
if [r["id"] for r in rows.values()] != [f"A{i:05d}" for i in range(1, 4809)]:
    raise ValueError("字表序號不完整")
idiom_words = {entry["word"]: entry for entry in idiom_data["records"]}
if not set(direct_links) <= idiom_words.keys():
    raise ValueError("成語直連表包含教育部正文以外的詞目")
idioms_by_char = defaultdict(list)
for entry in idiom_data["records"]:
    for char in set(entry["word"]):
        if char in rows:
            idioms_by_char[char].append(entry)
families, radicals, sounds, meanings, py, zy = (defaultdict(list) for _ in range(6))
for sound, entries in ed["roles"].items():
    for char, meaning in entries.items():
        rows[char].update(phonetic=sound, semantic=meaning)
        sounds[sound].append(char)
        meanings[meaning].append(char)

for char, row in rows.items():
    row["structure"], row["components"] = decomposition(row["ids"], char)
    for part in row["components"]:
        families[part].append(char)
    radicals[row["radical"]].append(char)
    for z, p in row["readings"]:
        py[p].append(char)
        zy[z].append(char)
    official_entries = idioms_by_char[char]
    official_words = {entry["word"] for entry in official_entries}
    row["idiom_entries"] = official_entries
    row["editorial_idioms"] = [
        word for word in ed["idioms"].get(char, []) if word not in official_words
    ]
    row["idioms"] = list(dict.fromkeys(
        [entry["word"] for entry in official_entries] + ed["idioms"].get(char, [])
    ))
    row["etymology"] = ed["notes"].get(char, "")
    row["groups"] = [g["chars"] for g in ed["groups"] if char in g["chars"]]

for group in ed["groups"]:
    if not set(group["chars"]) <= rows.keys():
        raise ValueError("易混淆群含表外字")

for name, obj in [("chars",rows), ("families",families), ("radicals",radicals), ("pinyin",py),
                  ("zhuyin",zy), ("idioms",idiom_data), ("etymology",ed["notes"]),
                  ("confusion",ed["groups"]), ("phonetics",sounds), ("semantics",meanings), ("audit",audit)]:
    dump(name,obj)
shutil.copyfile(SRC/"idioms-usage.odt", DOC/"data"/"idioms-usage.odt")

# Posting lists use indices in official order. Full-text fields remain searchable
# by substring; readings use exact syllables so a marked tone stays selective.
index = defaultdict(lambda: defaultdict(list))
for i, (c, r) in enumerate(rows.items()):
    fields = {"單字":[c], "序號":[r["id"].lower(), "u+"+code(c)], "部首":[r["radical"]],
              "部件":list(r["components"]), "字族":[k+"字族" for k in r["components"]],
              "注音":[z for z,p in r["readings"]], "拼音":[p for z,p in r["readings"]],
              "成語":r["idioms"],
              "成語注音":[e["zhuyin"] for e in r["idiom_entries"]],
              "成語拼音":[e["pinyin"] for e in r["idiom_entries"]],
              "字源":[r["etymology"]], "易混淆":r["groups"]}
    fields["拼音"].extend(unicodedata.normalize("NFC", "".join(ch for ch in unicodedata.normalize("NFD", p)
                             if ch not in "\u0304\u0301\u030c\u0300")) for z,p in r["readings"])
    if "phonetic" in r:
        fields.update(聲旁=[r["phonetic"],r["phonetic"]+"系"], 形旁=[r["semantic"]])
    for field, terms in fields.items():
        for term in set(terms) - {""}:
            index[field][term].append(i)
search = dict(chars="".join(rows), families="".join(sorted(families)), fields=index)
dump("search-index", search)
write("assets/index.js", "const HAN_INDEX="+packed(search)+";\n")
for name in ("app.js","app.css"):
    shutil.copyfile(ROOT/"web"/name, DOC/"assets"/name)
shutil.copyfile(SRC/"Unicode-LICENSE.txt", DOC/"data"/"Unicode-LICENSE.txt")
write(".nojekyll","")
page("index.html", TITLE, f'''<p class="eyebrow">教育部常用國字 · 4,808 字</p>
<p>從一個字音、一筆部件，找到同族的字。</p>
<label for="query">全文搜尋</label><input type="search" id="query" placeholder="試試：䍃、ㄧㄠˊ、扶搖直上">
<noscript>全文搜尋需要 JavaScript；各分類目錄仍可直接瀏覽。</noscript>
<p id="status" role="status"></p><section id="matches"></section>
<h2>從字族開始</h2><div class="tiles">{"".join(family(c) for c in "䍃青包可羊甫")}</div>
<h2>索引目錄</h2><div class="tiles">{"".join(link(k+".html",v) for k,v in NAV.items())}</div>
<script src="assets/index.js"></script><script src="assets/app.js"></script>''')

for name, groups in [("radicals",radicals),("families",families),("phonetics",sounds),("semantics",meanings)]:
    sections = []
    for key in sorted(groups):
        members = groups[key]
        dest = family(key) if name == "families" else ""
        singleton = ' data-singleton' if len(members) == 1 else ""
        sections.append(f'<details id="u{code(key)}"{singleton}><summary>{key} · {len(members)} 字</summary>{dest}{tiles(members)}</details>')
    page(name+".html",NAV[name],group_filter("".join(sections)))

for part, members in families.items():
    content = f"<p>原表中有 {len(members)} 字的臺灣字形拆解含「{part}」。共有部件不一定就是共同聲旁。</p>"
    if part in rows:
        content += link(f"../char/{code(part)}.html","查「"+part+"」本字")
    for label, subset in [("直接部件",[c for c in members if rows[c]["components"][part]==1]),
                          ("內嵌部件",[c for c in members if rows[c]["components"][part]>1])]:
        if subset:
            content += f"<details open><summary>{label} · {len(subset)} 字</summary>{tiles(subset,'../')}</details>"
    page("family/"+code(part)+".html",part+"字族",content)

sections = []
for g in ed["groups"]:
    singleton = ' data-singleton' if len(g["chars"]) == 1 else ""
    sections.append(f'<details open id="u{code(g["chars"][0])}"{singleton}><summary>{"／".join(g["chars"])}</summary><p>{g["note"]}</p>{tiles(g["chars"])}</details>')
page("confusion.html",NAV["confusion"],group_filter("".join(sections)))


def idiom_url(word):
    verified_id = direct_links.get(word)
    if verified_id:
        return f"https://dict.idioms.moe.edu.tw/idiomView.jsp?ID={verified_id}&q=1"
    return ("https://dict.idioms.moe.edu.tw/idiomList.jsp?idiom=" + quote(word, safe="") +
            "&qMd=0&qTp=1")


def idiom_reading(text):
    parts = text.split("（變）")
    if len(parts) == 1:
        return escape(text)
    return escape(parts[0].rstrip()) + "".join(
        "<br>（變）" + escape(part) for part in parts[1:]
    )


def idiom_list(char, row):
    entries = []
    for entry in row["idiom_entries"]:
        entries.append(
            f'<li><div>{link(idiom_url(entry["word"]), entry["word"])}</div>'
            f'<div class="idiom-reading">{idiom_reading(entry["zhuyin"])}</div>'
            f'<div class="idiom-reading">{idiom_reading(entry["pinyin"])}</div>'
            f'<small>{escape(entry["category"])}</small></li>'
        )
    for word in row["editorial_idioms"]:
        entries.append(
            f'<li><div>{link(idiom_url(word), word)}</div>'
            '<small>編輯選錄</small></li>'
        )
    count = len(entries)
    appendix = ("https://dict.idioms.moe.edu.tw/idiomList.jsp?idiom=" +
                quote(char, safe="") + "&qMd=0&qTp=2")
    return (f'<details class="idiom-panel"><summary>{count} 條 · 教育部正文及編輯選錄</summary>'
            f'<ul class="idiom-list">{"".join(entries)}</ul>'
            f'<p>{link(appendix, "另查教育部《成語典》附錄（需網路）")}</p></details>')


for c, r in rows.items():
    role = (link("../phonetics.html#u"+code(r["phonetic"]),r["phonetic"])+" ／ "+
            link("../semantics.html#u"+code(r["semantic"]),r["semantic"])) if "phonetic" in r else UNKNOWN
    groups = "、".join(link("../confusion.html#u"+code(g[0]),g) for g in r["groups"])
    partlinks = "、".join(family(k,"../") for k in r["components"])
    readings = "、".join(z+"（"+p+"）" for z,p in r["readings"])
    unihan = "；".join(k+"："+v for k,v in r["unihan"].items())
    related = [k for k in sounds.get(r.get("phonetic"),[]) if k!=c]
    facts = [("注音／漢語拼音",readings),("部首／總筆畫",link("../radicals.html#u"+code(r["radical"]),r["radical"])+f' ／ {r["strokes"]} 畫'),
             ("結構／字形拆解",r["structure"]+" ／ "+escape(r["ids"])),("部件字族",partlinks or "來源未再拆分"),
             ("聲旁／形旁（編輯整理）",role),("易混淆字群",groups or "未收錄"),
             ("成語／注音／漢語拼音",idiom_list(c,r) if r["idiom_entries"] or r["editorial_idioms"] else "未收錄"),
             ("字源筆記",r["etymology"] or "待考")]
    body = f'<p class="eyebrow">{r["id"]} · U+{code(c).upper()} · 教育部原表第 {r["page"]} 頁</p><dl>'
    body += "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label,value in facts)+"</dl>"
    if related:
        body += "<h2>相關字 · 同聲旁</h2>"+tiles(related,"../")
    body += f'<details><summary>來源與對照</summary><p>全字庫 {r["cns"]}；BabelStone IDS 臺灣字形。</p><p>{escape(unihan)}</p>'
    body += link("../sources.html","資料欄位與來源")+" · "+link("https://www.zdic.net/hans/"+c,"查《說文解字》等字書 · "+c)+"</details>"
    page("char/"+code(c)+".html",c,body)

page("sources.html",NAV["sources"],f'''<h2>字表核對</h2><p>依教育部
<a href="https://language.moe.gov.tw/001/Upload/Files/site_content/download/mandr/教育部4808個常用字.pdf">《教育部4808個常用字》</a>逐列匯入。A00001–A04808 無缺號、重號或重字。
A02149 的原表圖像與碼位欄均為「汩」(6C69)；PDF 文字擷取誤讀為「汨」，本站依原表收錄「汩」(U+6C69)。<a href="data/audit.json">核對報告與檔案雜湊</a></p>
<h2>資料覆蓋</h2><ul><li>含臺灣讀音 {sum(bool(r["readings"]) for r in rows.values())} 字；部首、筆畫及臺灣 IDS 各 {len(rows)} 字。</li>
<li>編輯整理聲形角色 {sum(map(len,sounds.values()))} 字；字源筆記 {len(ed["notes"])} 字；易混淆字群 {len(ed["groups"])} 組。
「待考」不是無聲旁；未收錄成語不表示該字沒有成語。</li></ul>
<h2>教育部《成語典》</h2><p>中華民國教育部（Ministry of Education, R.O.C.）。《成語典》（版本編號：{idiom_data["version"]}），
<a href="https://dict.idioms.moe.edu.tw/">教育部《成語典》</a>。正文詞目、注音、漢語拼音均依教育部資料原文呈現；本站僅建立逐字索引及外部查詢連結，不改寫個別詞目內容。
本版收錄 {len(idiom_data["records"])} 筆正文成語，涉及 {sum(bool(r["idiom_entries"]) for r in rows.values())} 個常用字。官方資料採
<a href="https://creativecommons.org/licenses/by-nd/3.0/tw/">創用 CC 姓名標示－禁止改作 3.0 臺灣授權條款</a>；
<a href="data/idioms-usage.odt">完整保留教育部公眾授權使用說明</a>，亦可查閱
<a href="https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/dict_idiomsdict_download.html">教育部官方資料下載頁</a>。
逐字頁所列正文及讀音可離線瀏覽；少數已核實詞目使用教育部直連，其餘連至官方精確詞目搜尋。辭典附錄未包含於離線資料，另提供需網路的教育部查詢連結。</p>
<h2>來源與界線</h2><ul><li>數位發展部，<a href="https://www.cns11643.gov.tw">CNS11643中文標準交換碼全字庫網站</a>：
注音、漢語拼音、部首與筆畫，依<a href="https://www.cns11643.gov.tw/pageView.jsp?ID=59">政府資料開放授權條款第1版</a>整理。</li>
<li>Andrew West，<a href="https://www.babelstone.co.uk/CJK/IDS.TXT">BabelStone IDS</a>（2025-06-27，自由使用）：僅取 T 地區序列。直接／內嵌依這一條序列的層次區別，不把所有可遞迴拆分的筆畫算作字族。「未再拆分」不是字源判定。</li>
<li><a href="https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip">Unicode Unihan 17.0</a>：kRSUnicode、kTotalStrokes、kMandarin、廣韻（kSBGY）、漢語大字典（kHanYu）與異體對照欄依原值並列；不覆蓋臺灣資料。<a href="data/Unicode-LICENSE.txt">Unicode 授權</a></li>
<li>聲旁、形旁、成語與辨形筆記為本版選編，非教育部或中研院審定。字頁另附字書查考入口。延伸查考：<a href="https://dict.variants.moe.edu.tw/">教育部異體字字典</a>、
<a href="https://xiaoxue.iis.sinica.edu.tw/">中研院小學堂</a>；未重製其釋文、歷代字形或圖像。</li></ul>''')
print(f"Built {len(rows)} character pages and {len(families)} family pages.")
