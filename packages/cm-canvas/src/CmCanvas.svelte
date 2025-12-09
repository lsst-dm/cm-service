<script lang="ts">
  import Dagre from "@dagrejs/dagre";
  import {
    Background,
    BackgroundVariant,
    Controls,
    MiniMap,
    Panel,
    SvelteFlow,
    useSvelteFlow,
    type Edge,
    type Node,
    type NodeTypes,
    type OnConnectEnd,
  } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";

  import StartNode from "./StartNode.svelte";
  import EndNode from "./EndNode.svelte";
  import StepNode from "./StepNode.svelte";
  import { MarkerType, Position } from "@xyflow/system";
  import { onMount, tick } from "svelte";

  type CanvasProps = {
    nodes?: Node[];
    edges?: Edge[];
    onClick?: (nodeId: string) => void;
    onExport?: any;
  }

  /* A mapping of custom node names to their implementation. The names used in
     mapping mirror the ManifestKind enum names used in the CM application.
  */
  const nodeTypes = {
    start: StartNode,
    end: EndNode,
    step: StepNode,
  } as any as NodeTypes;

  /* the $props rune defines the inputs to the component, which can be used as
     arguments or attributes when the component is initialized.
  */
  let {
    nodes,
    edges,
    onClick = null,
    onExport = null,
  }: CanvasProps = $props();

  let id = $derived(nodes.length + 1);

  // functions provided by the Svelte-Flow
  const { screenToFlowPosition, fitView } = useSvelteFlow();

  const getId = () => `${id++}`;

  const handleConnectEnd: OnConnectEnd = (event, connectionState) => {
    if (connectionState.isValid) return;

    const targetHandle =
      connectionState.fromPosition == "bottom" ? "top" : "left";
    const sourceHandle = connectionState.fromHandle?.position;
    const sourceNodeId = connectionState.fromNode?.id ?? "1";
    const id = getId();
    const { clientX, clientY } =
      "changedTouches" in event ? event.changedTouches[0] : event;

    const newNode: Node = {
      type: "step",
      id,
      data: { name: `step_${id}`, handleClick: onClick },
      position: screenToFlowPosition({ x: clientX, y: clientY }),
    };

    nodes = [...nodes, newNode];
    edges = [
      ...edges,
      {
        source: sourceNodeId,
        target: id,
        id: `${sourceNodeId}--${id}`,
        sourceHandle: sourceHandle,
        targetHandle: targetHandle,
        type: "smoothstep",
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      },
    ];
  };

  // export handler, called from python with `canvasExport` event, listener
  // expecting "return" event `canvasExported`
  window.addEventListener("canvasExport", () => {
    console.log("Canvas received canvasExport event");
    const serializedCanvas = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };
    window.dispatchEvent(
      new CustomEvent("canvasExported", {
        detail: { data: serializedCanvas },
      }),
    );
    console.log("Canvas dispatched canvasExported event");
  });

  // Auto-layout function using Dagre, basically copy-pasted from svelte-flow
  // layouting documentation example
  async function getLayoutedElements(nodes, edges, options) {
    const isHorizontal = options.direction === "LR";
    const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: options.direction });

    edges.forEach((edge) => g.setEdge(edge.source, edge.target));
    nodes.forEach((node) => g.setNode(node.id, { width: 172, height: 60 }));

    Dagre.layout(g);

    return {
      nodes: nodes.map((node) => {
        const positionedNode = g.node(node.id);
        return {
          ...node,
          position: {
            x: positionedNode.x - 172 / 2,
            y: positionedNode.y - 60 / 2,
          },
          sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
          targetPosition: isHorizontal ? Position.Left : Position.Top,
        };
      }),
      edges: edges.map((edge) => {
        return {
          ...edge,
          sourceHandle: isHorizontal ? "right" : "bottom",
          targetHandle: isHorizontal ? "left" : "top",
          type: "smoothstep",
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        };
      }),
    };
  }

  async function onLayout(direction) {
    const layouted = await getLayoutedElements(nodes, edges, { direction });
    nodes = [...layouted.nodes];
    edges = [...layouted.edges];
    await tick();
    // Only if we need some extra sleep after tick
    // await new Promise(resolve => setTimeout(resolve, 100));
    fitView({ padding: 0.2 });
  }

  onMount(async () => {
    onLayout("LR");
    await tick();
    await new Promise((resolve) => setTimeout(resolve, 150));
    fitView({ padding: 0.2 });
  });
</script>

<SvelteFlow
  bind:nodes
  bind:edges
  {nodeTypes}
  {onClick}
  fitView
  onconnectend={handleConnectEnd}
  proOptions={{ hideAttribution: true }}
  nodeOrigin={[0.5, 0.5]}
>
  <Controls />
  <Background variant={BackgroundVariant.Dots} />
  <MiniMap nodeStrokeWidth={3} />
  <Panel position="top-right">
    <button class="panel-btn" onclick={() => onLayout("TB")}
      >Vertical Layout</button
    >
    <button class="panel-btn" onclick={() => onLayout("LR")}
      >Horizontal Layout</button
    >
  </Panel>
</SvelteFlow>

<style>
  :global(.svelte-flow__handle) {
    opacity: 0;
    transition: opacity 0.2s;
  }

  :global(.svelte-flow__handle.valid) {
    opacity: 1;
    background: var(--rubin-color-green-dark);
  }

  :global(.svelte-flow__node:hover .svelte-flow__handle) {
    opacity: 0.5;
  }

  :global(
    .svelte-flow__edge:hover,
    .svelte-flow__edge.selectable:hover path.svelte-flow__edge-path,
    .svelte-flow__edge.selectable.selected path.svelte-flow__edge-path
  ) {
    stroke: var(--rubin-color-orange-light);
    stroke-width: 2;
    transition: fill 0.2s;
  }

  :global(.svelte-flow__node) {
    border: 2px solid rgba(0, 0, 0, 0);
  }

  :global(.svelte-flow__node.selected) {
    border: 2px solid var(--rubin-color-violet-light);
  }

  .panel-btn {
    padding: 8px 16px;
    background: var(--rubin-color-white-light);
    border: 1px solid var(--rubin-color-grey-light);
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .panel-btn:hover {
    background: var(--rubin-color-white-dark);
  }
</style>
