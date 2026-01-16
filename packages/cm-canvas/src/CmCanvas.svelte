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
  import BreakpointNode from "./BreakpointNode.svelte";
  import { useDragDrop } from "./DragDropProvider.svelte";
  import { MarkerType, Position } from "@xyflow/system";
  import { onMount, tick } from "svelte";

  type CanvasProps = {
    nodes?: Node[];
    edges?: Edge[];
    onClick?: (nodeId: string) => void;
    onExport?: any;
  };

  /* A mapping of custom node names to their implementation. The names used in
     mapping mirror the ManifestKind enum names used in the CM application.
  */
  const nodeTypes = {
    start: StartNode,
    end: EndNode,
    step: StepNode,
    breakpoint: BreakpointNode,
  } as any as NodeTypes;

  /* the $props rune defines the inputs to the component, which can be used as
     arguments or attributes when the component is initialized.
  */
  let { nodes, edges, onClick = null, onExport = null }: CanvasProps = $props();

  let id = $derived(nodes.length + 1);

  // functions provided by the Svelte-Flow
  const { screenToFlowPosition, fitView } = useSvelteFlow();

  const getId = () => `${id++}`;
  const type = useDragDrop();
  const onDragStart = (event: DragEvent, nodeType: string) => {
    if (!event.dataTransfer) {
      return null;
    }
    type.current = nodeType;
    event.dataTransfer.effectAllowed = "move";
  };
  const onDragOver = (event: DragEvent) => {
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "move";
    }
  };
  const onDrop = (event: DragEvent) => {
    const id = getId();
    event.preventDefault();
    if (!type.current) {
      return;
    }
    const position = screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    const newNode = {
      type: type.current,
      id,
      position,
      data: { name: `${type.current}_${id}`, handleClick: onClick },
    } satisfies Node;
    nodes = [...nodes, newNode];
  };

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

<div class="cmcanvas">
  <SvelteFlow
    bind:nodes
    bind:edges
    {nodeTypes}
    {onClick}
    fitView
    onconnectend={handleConnectEnd}
    ondragover={onDragOver}
    ondrop={onDrop}
    proOptions={{ hideAttribution: true }}
    nodeOrigin={[0.5, 0.5]}
  >
    <Controls />
    <Background variant={BackgroundVariant.Dots} />
    <MiniMap nodeStrokeWidth={3} />
    <Panel position="top-left">
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <div class="panel-container">
        <div
          class="panel-icon clickable"
          role="button"
          tabindex="0"
          onclick={() => onLayout("TB")}
          title="Layout graph top-to-bottom"
        >
          <svg
            class="panel-icon"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 -960 960 960"
            ><path
              d="m480-220 160-160-56-56-64 64v-216l64 64 56-56-160-160-160 160 56 56 64-64v216l-64-64-56 56 160 160Zm0 140q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q133 0 226.5-93.5T800-480q0-133-93.5-226.5T480-800q-133 0-226.5 93.5T160-480q0 133 93.5 226.5T480-160Zm0-320Z"
            /></svg
          >
        </div>
        <div
          class="panel-icon clickable"
          role="button"
          tabindex="0"
          onclick={() => onLayout("LR")}
          title="Layout graph left-to-right"
        >
          <svg
            class="panel-icon"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 -960 960 960"
            ><path
              d="M480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q133 0 226.5-93.5T800-480q0-133-93.5-226.5T480-800q-133 0-226.5 93.5T160-480q0 133 93.5 226.5T480-160Zm0-320ZM380-320l56-56-64-64h216l-64 64 56 56 160-160-160-160-56 56 64 64H372l64-64-56-56-160 160 160 160Z"
            /></svg
          >
        </div>
      </div>
    </Panel>
    <Panel position="top-right">
      <div class="panel-container">
        <svg
          class="panel-icon"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 -960 960 960"
          ><path
            d="M440-280h80v-160h160v-80H520v-160h-80v160H280v80h160v160Zm40 200q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"
          /></svg
        >
        <div
          class="draggable panel-btn"
          role="button"
          tabindex="0"
          draggable={true}
          ondragstart={(event) => onDragStart(event, "step")}
          title="Drag to create a Step"
        >
          Step
        </div>
        <div
          class="draggable panel-btn"
          role="button"
          tabindex="0"
          draggable={true}
          ondragstart={(event) => onDragStart(event, "breakpoint")}
          title="Drag to create a Breakpoint"
        >
          Breakpoint
        </div>
      </div>
    </Panel>
  </SvelteFlow>
</div>

<style>
  .cmcanvas {
    height: 100%;
    display: flex;
    flex-direction: column-reverse;
  }
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

  .panel-container {
    font-family: "Source Sans Pro", "Roboto", sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .panel-btn {
    padding: 8px 16px;
    background: var(--rubin-color-white-light);
    border: 1px solid var(--rubin-color-grey-light);
    border-radius: 4px;
    font-size: 14px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    user-select: none;
    font-weight: 500;
    font-style: italic;
  }

  .panel-btn:hover {
    background: var(--rubin-color-white-dark);
  }

  .panel-icon {
    display: block;
    flex-shrink: 0;
    height: 32px;
    width: 32px;
    fill: var(--rubin-color-black-light);
  }

  .panel-icon:hover {
    background: var(--rubin-color-white-dark);
  }

  .draggable {
    cursor: grab;
    -webkit-user-drag: element;
    -webkit-transform: translateZ(0);
  }

  .draggable:active {
    cursor: grabbing;
  }

  .clickable {
    cursor: pointer;
  }
</style>
