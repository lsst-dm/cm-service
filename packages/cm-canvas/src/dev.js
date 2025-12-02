import { mount } from "svelte";
import App from "./App.svelte";

mount(App, {
  target: document.getElementById("app"),
  props: {
    onExport: (data) => {
      console.log("Export callback fired!");
      console.log("Nodes:", data.nodes);
      console.log("Edges:", data.edges);
      alert(
        `Exported ${data.nodes.length} nodes and ${data.edges.length} edges`,
      );
    },
  },
});
