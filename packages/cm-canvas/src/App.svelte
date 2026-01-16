<script lang="ts">
  import "@xyflow/svelte/dist/style.css";
  import { SvelteFlowProvider, type Node, type Edge } from "@xyflow/svelte";
  import CmCanvas from "./CmCanvas.svelte";
  import DragDropProvider from "./DragDropProvider.svelte";

  type CanvasProps = {
    nodes?: Node[];
    edges?: Edge[];
    [key: string]: any;
  };

  /* A set of defaultNodes for an otherwise empty canvas. Because a CM campaign
    always has a definite START and END, these are included. Although this canvas
    component does not perform graph validation, the CM server will not allow an
    invalid campaign graph to enter a running state.
    */
  const defaultNodes: Node[] = [
    {
      id: "START",
      type: "start",
      position: { x: 0, y: 0 },
      data: { name: "START" },
    },
    {
      id: "END",
      type: "end",
      position: { x: 0, y: 0 },
      data: { name: "END" },
    },
  ];

  /* A set of props to send to the Canvas component
   */
  let {
    nodes: incomingNodes,
    edges: incomingEdges,
    ...restProps
  }: CanvasProps = $props();

  /* If no nodes or an empty nodes list is provided, use the default set. Also
  ensure the onClick prop is applied to the Node's handleClick data attribute
  if the node is an editable type like "step"
  */
  let nodes = $derived(
    (!incomingNodes || incomingNodes.length === 0
      ? defaultNodes
      : incomingNodes
    ).map((node) => {
      if (node.type === "step") {
        return {
          ...node,
          data: {
            ...node.data,
            handleClick: restProps.onClick,
          },
        };
      }
      return node;
    }),
  );

  let edges = $derived(
    !incomingEdges || incomingEdges.length === 0 ? [] : incomingEdges,
  );
</script>

<SvelteFlowProvider>
  <DragDropProvider>
    <CmCanvas {nodes} {edges} {...restProps} />
  </DragDropProvider>
</SvelteFlowProvider>

<style>
  :root {
    --rubin-color-red-light: #fa6868;
    --rubin-color-orange-light: #ffc036;
    --rubin-color-yellow-light: #fff3a1;
    --rubin-color-green-light: #55da59;
    --rubin-color-blue-light: #00babc;
    --rubin-color-indigo-light: #0099d5;
    --rubin-color-violet-light: #cd84ec;
    --rubin-color-black-light: #313333;
    --rubin-color-white-light: #f5f5f5;
    --rubin-color-grey-light: #6a6e6e;
    --rubin-color-red-dark: #cf4040;
    --rubin-color-orange-dark: #e08d35;
    --rubin-color-yellow-dark: #ffb71b;
    --rubin-color-green-dark: #019305;
    --rubin-color-blue-dark: #058b8c;
    --rubin-color-indigo-dark: #005684;
    --rubin-color-violet-dark: #652291;
    --rubin-color-black-dark: #1f2121;
    --rubin-color-white-dark: #dce0e3;
    --rubin-color-grey-dark: #6a6e6e;
  }
</style>
