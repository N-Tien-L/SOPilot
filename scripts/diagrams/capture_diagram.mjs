// Headless renderer used by capture_diagram.py. Loads a viewer page written by excalidraw_builder.py,
// waits for the scene and its fonts, then exports through Excalidraw's own exportToBlob/exportToSvg,
// which crop to the elements' bounding box plus the padding. Playwright is resolved from the local
// Excalidraw clone (--tools-dir), so this repository gains no Node dependency.
import { createRequire } from "node:module";
import { writeFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, cur, i, all) => {
    if (cur.startsWith("--")) acc.push([cur.slice(2), all[i + 1]]);
    return acc;
  }, []),
);
const html = resolve(args.html);
const out = resolve(args.out);
const format = args.format ?? "png";
const scale = Number(args.scale ?? 2);
const padding = Number(args.padding ?? 20);
const theme = args.theme ?? "auto";
const timeout = Number(args.timeout ?? 60000);
const toolsDir = resolve(args["tools-dir"]);

const pkg = join(toolsDir, "package.json");
if (!existsSync(pkg)) {
  console.error(`capture: no package.json in tools dir ${toolsDir}`);
  process.exit(2);
}
let chromium;
try {
  ({ chromium } = createRequire(pkg)("playwright"));
} catch {
  console.error(`capture: playwright is not installed in ${toolsDir} (run 'yarn' there)`);
  process.exit(2);
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ deviceScaleFactor: scale, viewport: { width: 1600, height: 1000 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(pathToFileURL(html).href, { waitUntil: "load", timeout });
  try {
    await page.waitForFunction(() => window.excalidrawAPI && window.ExcalidrawLib, null, { timeout });
  } catch (e) {
    console.error(`capture: Excalidraw did not start (offline? esm.sh unreachable?) ${errors.join(" | ")}`);
    throw e;
  }
  const result = await page.evaluate(
    async ({ format, scale, padding, theme }) => {
      const families = ["Excalifont", "Nunito", "Comic Shanns", "Lilita One", "Virgil"];
      await Promise.allSettled(families.map((f) => document.fonts.load(`20px "${f}"`)));
      await document.fonts.ready;
      await new Promise((r) => setTimeout(r, 800)); // let Excalidraw re-measure text after font load
      const api = window.excalidrawAPI;
      const { exportToBlob, exportToSvg } = window.ExcalidrawLib;
      const base = api.getAppState();
      const dark = theme === "auto" ? base.theme === "dark" : theme === "dark";
      const elements = api.getSceneElements();
      if (!elements.length) throw new Error("scene has no elements");
      const appState = {
        ...base,
        exportBackground: true,
        exportWithDarkMode: dark,
        exportScale: format === "svg" ? 1 : scale, // SVG is vector: keep natural size
        exportEmbedScene: false,
      };
      const opts = { elements, appState, files: api.getFiles(), exportPadding: padding };
      if (format === "svg") {
        const svg = await exportToSvg(opts);
        return { kind: "svg", data: svg.outerHTML, w: svg.getAttribute("width"), h: svg.getAttribute("height"), n: elements.length };
      }
      // exportToBlob ignores appState.exportScale in 0.18; getDimensions applies the pixel ratio.
      const getDimensions = (width, height) => ({ width: width * scale, height: height * scale, scale });
      const blob = await exportToBlob({ ...opts, getDimensions, mimeType: "image/png" });
      const bmp = await createImageBitmap(blob);
      const buf = new Uint8Array(await blob.arrayBuffer());
      let bin = "";
      for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
      return { kind: "png", data: btoa(bin), w: bmp.width, h: bmp.height, n: elements.length };
    },
    { format, scale, padding, theme },
  );
  writeFileSync(out, result.kind === "png" ? Buffer.from(result.data, "base64") : result.data);
  console.log(`captured ${out} (${result.kind}, ${result.w}x${result.h}, ${result.n} elements)`);
} finally {
  await browser.close();
}
