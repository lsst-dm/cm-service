import { mount } from "svelte";
import App from "./App.svelte";

mount(App, {
  target: document.getElementById("app"),
  props: {
    nodes: [
      {
        id: "1",
        type: "start",
        data: { name: "Node A" },
        position: { x: 0, y: 0 },
      },
      {
        id: "2",
        type: "step",
        data: { name: "Node B" },
        position: { x: 0, y: 0 },
      },
      {
        id: "3",
        type: "step",
        data: { name: "Node C" },
        position: { x: 0, y: 0 },
      },
      {
        id: "4",
        type: "end",
        data: { name: "Node D" },
        position: { x: 0, y: 0 },
      },
    ],
    edges: [
      { id: "1--2", source: "1", target: "2" },
      { id: "2--3", source: "2", target: "3" },
      { id: "3--4", source: "3", target: "4" },
    ],
    onClick: (data) => {
      console.log("A node was clicked!");
      console.log("Node", data);
      alert(`Custom onClick called: ${data}`);
    },
    onExport: (data) => {
      console.log("Export callback fired!");
      console.log("Nodes:", data.nodes);
      console.log("Edges:", data.edges);
      alert(`Exported ${data.nodes.length} nodes and ${data.edges.length} edges`,);
    },
  },
});
