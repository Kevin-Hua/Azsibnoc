"use strict";
const input = document.querySelector("#query");
const statusLine = document.querySelector("#status");
const results = document.querySelector("#matches");
const characters = Array.from(HAN_INDEX.chars);
const familyKeys = new Set(HAN_INDEX.families);
function anchor(folder, key, label) {
  const a = document.createElement("a");
  a.href = `${folder}/${key.codePointAt(0).toString(16).padStart(4,"0")}.html`;
  a.textContent = label;
  return a;
}
function search() {
  results.replaceChildren();
  const q = input.value.trim().normalize("NFC").toLowerCase();
  statusLine.textContent = "";
  if (!q) return;
  const part = q.replace(/字族$/, "");
  const family = familyKeys.has(part);
  if (family) results.append(anchor("family", part, `查看「${part}」字族`));
  const hits = new Map();
  for (const [field, terms] of Object.entries(HAN_INDEX.fields)) {
    const text = ["成語","成語注音","成語拼音","字源","易混淆"].includes(field);
    const postings = text ? Object.entries(terms).filter(([t]) => t.includes(q)).map(([,ids]) => ids) :
      Object.hasOwn(terms,q) ? [terms[q]] : [];
    for (const ids of postings) for (const id of ids) {
      if (!hits.has(id)) hits.set(id,new Set());
      hits.get(id).add(field);
    }
  }
  statusLine.textContent = hits.size || family ? `找到 ${hits.size} 個字${family ? "、1 個字族" : ""}` : "找不到符合的字或字族。";
  const list = document.createElement("div");
  list.className = "tiles";
  const entries = [...hits];
  let offset = 0;
  const more = document.createElement("button");
  more.textContent = "顯示更多結果";
  function appendBatch() {
    for (const [id,fields] of entries.slice(offset,offset+80)) {
      list.append(anchor("char",characters[id],`${characters[id]} · ${[...fields].join("／")}`));
    }
    offset += 80;
    more.hidden = offset >= entries.length;
  }
  results.append(list,more);
  more.onclick = appendBatch;
  appendBatch();
}
input.addEventListener("input",search);
search();
