if (typeof process === "undefined") {
  window.process = { env: {} };
}

import { mount } from "svelte";
import App from "./App.svelte";

export function initializeFlow(containerId, options = {}) {
  const container = document.getElementById(containerId);

  if (!container) {
    console.error("Container #${containerId} not found");
    return null;
  }

  const canvas = mount(App, {
    target: container,
    props: {
      nodes: options.nodes,
      edges: options.edges,
      onExport: options.onExport,
      onClick: options.onClick,
    },
  });

  return {
    canvas,
  };
}

if (typeof window !== "undefined") {
  window.initializeFlow = initializeFlow;
}
