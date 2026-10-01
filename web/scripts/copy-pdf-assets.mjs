// Ship PDF.js CMaps, fallback fonts and decoders locally; never fetch a third-party CDN.
import { cpSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "node_modules/pdfjs-dist");
const target = resolve(root, "public/pdfjs");
mkdirSync(target, { recursive: true });
for (const folder of ["cmaps", "standard_fonts", "wasm", "iccs"]) {
  cpSync(resolve(source, folder), resolve(target, folder), { recursive: true });
}
cpSync(resolve(source, "LICENSE"), resolve(target, "LICENSE"));
