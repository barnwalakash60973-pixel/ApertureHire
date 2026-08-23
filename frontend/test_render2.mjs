import { JSDOM, VirtualConsole } from "jsdom";

const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", (err) => {
  console.log("=== JSDOM ERROR ===", err.message);
  if (err.detail?.stack) console.log(err.detail.stack);
});
virtualConsole.on("log", (...a) => console.log("PAGE LOG:", ...a));
virtualConsole.on("warn", (...a) => console.log("PAGE WARN:", ...a));
virtualConsole.on("error", (...a) => console.log("PAGE ERROR:", ...a));
virtualConsole.on("info", (...a) => console.log("PAGE INFO:", ...a));

const dom = await JSDOM.fromURL("http://localhost:4173/", {
  runScripts: "dangerously",
  resources: "usable",
  virtualConsole,
  pretendToBeVisual: true,
});

const { window } = dom;
window.addEventListener("error", (e) => {
  console.log("=== WINDOW ERROR EVENT ===");
  console.log(e.error?.stack || e.message);
});
window.addEventListener("unhandledrejection", (e) => {
  console.log("=== UNHANDLED REJECTION ===");
  console.log(e.reason?.stack || e.reason);
});

await new Promise((r) => setTimeout(r, 5000));

console.log("document.readyState:", window.document.readyState);
console.log("scripts on page:", window.document.scripts.length);
for (const s of window.document.scripts) console.log(" -", s.src);
console.log("root innerHTML length:", window.document.getElementById("root")?.innerHTML.length);

process.exit(0);
