import { build } from "esbuild";
import { mkdirSync, cpSync } from "fs";

// Build server
await build({
  entryPoints: ["src/server.ts"],
  bundle: true,
  outfile: "build/server/index.js",
  format: "esm",
  target: "esnext",
  platform: "neutral",
  minify: false,
  external: [],
});

// Copy client files
mkdirSync("build/client", { recursive: true });
cpSync("public/index.html", "build/client/index.html");
cpSync("public/chart.min.js", "build/client/chart.min.js");

// Copy app manifest
cpSync("app.yaml", "build/app.yaml");

console.log("Build complete:");
console.log("  build/server/index.js");
console.log("  build/client/index.html");
console.log("  build/app.yaml");
