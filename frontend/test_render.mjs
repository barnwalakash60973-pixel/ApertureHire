import { JSDOM } from "jsdom";

const virtualConsole = new (await import("jsdom")).VirtualConsole();
let caughtError = null;

virtualConsole.on("jsdomError", (err) => {
  caughtError = err;
  console.log("JSDOM ERROR:", err.message);
  if (err.detail) console.log("DETAIL:", err.detail.stack || err.detail);
});
virtualConsole.on("error", (...args) => console.log("CONSOLE.ERROR:", ...args));
virtualConsole.on("warn", (...args) => console.log("CONSOLE.WARN:", ...args));
virtualConsole.on("log", (...args) => console.log("CONSOLE.LOG:", ...args));

const dom = await JSDOM.fromURL("http://localhost:4173/", {
  runScripts: "dangerously",
  resources: "usable",
  virtualConsole,
  pretendToBeVisual: true,
});

dom.window.addEventListener?.("error", (e) => console.log("WINDOW ERROR:", e.error?.stack || e.message));

await new Promise((r) => setTimeout(r, 3000));

const root = dom.window.document.getElementById("root");
console.log("=== ROOT INNER HTML LENGTH ===", root ? root.innerHTML.length : "NO ROOT ELEMENT");
console.log("=== ROOT INNER HTML (first 500 chars) ===");
console.log(root ? root.innerHTML.slice(0, 500) : "N/A");

process.exit(0);
