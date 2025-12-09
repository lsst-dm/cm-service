import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import cssInjectedByJsPlugin from "vite-plugin-css-injected-by-js";

export default defineConfig({
  plugins: [svelte(), cssInjectedByJsPlugin()],
  build: {
    lib: {
      entry: "./src/index.js",
      name: "RubinCampaignWrapper",
      fileName: "cm-canvas-bundle",
      formats: ["iife"],
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
        assetFileNames: "cm-canvas-bundle.[ext]",
      },
    },
  },
  define: {
    "process.env": {},
    "process.env.NODE_ENV": JSON.stringify("production"),
    global: "globalThis",
  },
});
