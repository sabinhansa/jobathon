import { copyFile, cp, mkdir, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");
const watch = process.argv.includes("--watch");

async function copyStatic() {
  await rm(dist, { recursive: true, force: true });
  await mkdir(join(dist, "popup"), { recursive: true });
  await mkdir(join(dist, "icons"), { recursive: true });
  await copyFile(join(root, "manifest.json"), join(dist, "manifest.json"));
  await copyFile(join(root, "src", "popup", "popup.html"), join(dist, "popup", "popup.html"));
  await copyFile(join(root, "src", "popup", "popup.css"), join(dist, "popup", "popup.css"));
  await cp(join(root, "icons"), join(dist, "icons"), { recursive: true });
}

const config = {
  entryPoints: {
    background: join(root, "src", "background.ts"),
    contentScript: join(root, "src", "contentScript.ts"),
    "popup/popup": join(root, "src", "popup", "popup.ts"),
  },
  bundle: true,
  outdir: dist,
  format: "iife",
  target: "chrome115",
  sourcemap: false,
  logLevel: "info",
};

await copyStatic();

if (watch) {
  const context = await esbuild.context(config);
  await context.watch();
  console.log("Watching Jobathon extension...");
} else {
  await esbuild.build(config);
}

