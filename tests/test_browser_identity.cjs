const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const crypto = require("node:crypto").webcrypto;
const source = fs.readFileSync("services/identity_component/index.html", "utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
function browser(storage = new Map()) {
  const events = {}, sent = [];
  const parent = {postMessage: msg => sent.push(msg)};
  const context = {crypto, Uint8Array, window: {parent, location:{origin:"https://studyboost.example"}, addEventListener: (name, fn) => events[name] = fn}, localStorage: {
    getItem: key => storage.get(key), setItem: (key, val) => storage.set(key, val)
  }};
  vm.runInNewContext(source, context);
  function render(rotation = "") { events.message({origin:"https://studyboost.example", source: parent, data:{type:"streamlit:render",args:{rotation}}}); }
  function value() { return sent.filter(msg => msg.type === "streamlit:setComponentValue").at(-1).value; }
  return {render, value, events, storage};
}
const a = browser(), b = browser();
a.render(); b.render();
assert.notEqual(a.value().token, b.value().token);
assert.match(a.value().token, /^[0-9a-f]{64}$/);
const reload = browser(a.storage); reload.render();
assert.equal(reload.value().token, a.value().token);
const old = a.value().token; a.render("rotate-1");
assert.notEqual(a.value().token, old);
const rotated = a.value().token; a.render("rotate-1");
assert.equal(a.value().token, rotated);
// Existing tabs follow browser rotation without reverting it.
reload.events.storage({key:"studyboost.privateIdentity.v1"});
assert.equal(reload.value().token, rotated);
reload.render("rotate-2");
a.events.storage({key:"studyboost.privateIdentity.v1"}); a.render("rotate-1");
assert.equal(a.value().token, reload.value().token);
console.log("Browser identity: separation, reload, rotation and cross-tab sync OK");
