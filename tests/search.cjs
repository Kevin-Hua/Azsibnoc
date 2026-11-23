// Exercise the shipped scripts and link targets without network or a server.
const {readFileSync} = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
class Element {
  constructor() { this.children=[]; this.value=""; }
  append(...elements) { this.children.push(...elements); }
  replaceChildren() { this.children=[]; }
  addEventListener(event, fn) { this[event]=fn; }
}
const elements = Object.fromEntries(["query","status","matches"].map(id=>["#"+id,new Element()]));
const document = {querySelector:s=>elements[s], createElement:()=>new Element()};
const ctx = vm.createContext({document});
for (const file of ["index.js","app.js"]) {
  vm.runInContext(readFileSync(path.join(__dirname,"../docs/assets",file),"utf8"),ctx);
}
function query(q) {
  const input=elements["#query"];
  input.value=q; input.input();
  const walk=e=>[e.href,...e.children.flatMap(walk)].filter(Boolean);
  return walk(elements["#matches"]);
}
for (const q of ["ㄧㄠˊ","yáo","yao"]) {
  const links=query(q);
  for (const ch of "搖謠遙瑤") assert.ok(links.includes(`char/${ch.codePointAt(0).toString(16)}.html`),q+ch);
}
for (const q of ["䍃","䍃字族"]) assert.equal(query(q)[0],"family/4343.html");
for (const q of ["扶搖直上","搖直","形聲","手部動作"]) assert.ok(query(q).includes("char/6416.html"));
assert.ok(query("清").includes("char/6e05.html"));
assert.ok(query("汩").includes("char/6c69.html"));
assert.deepEqual(query("汨"),[]);
for (const q of ["花天酒地", "huā tiān jiǔ dì", "ㄏㄨㄚ　ㄊㄧㄢ　ㄐㄧㄡˇ　ㄉㄧˋ"]) {
  assert.ok(query(q).includes("char/82b1.html"), q);
}
for (const q of ["ㄍㄨˇ", "gǔ", "ㄩˋ", "yù"]) {
  assert.ok(query(q).includes("char/6c69.html"), q);
}
for (const q of ["ㄇㄧˋ", "mì"]) {
  assert.ok(!query(q).includes("char/6c69.html"), q);
}
assert.ok(query("巳已").includes("char/5df1.html")); // 己 also belongs to this group
assert.deepEqual(query("not-a-word"),[]);
assert.match(elements["#status"].textContent,/找不到/);
assert.deepEqual(query(""),[]);
console.log("OK: offline search behavior and target links.");
