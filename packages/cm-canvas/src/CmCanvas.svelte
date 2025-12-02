<script lang="ts">
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


// A mapping of custom node names to their implementation
const nodeTypes = {
    startNode: StartNode,
    endNode: EndNode,
    stepNode: StepNode,
} as any as NodeTypes;


/* the $props rune defines the inputs to the component, which can be used as
arguments or attributes when the component is initialized.
*/
let {
    nodes = [],
    edges = [],
    onExport = null,
} = $props();

let id = 1;

// functions provided by the Svelte-Flow
const { screenToFlowPosition, toObject } = useSvelteFlow();

const getId = () => `${id++}`;

const handleConnectEnd: OnConnectEnd = (event, connectionState) => {
    if (connectionState.isValid) return;

    const sourceNodeId = connectionState.fromNode?.id ?? "1";
    const id = getId();
    const { clientX, clientY } = "changedTouches" in event ? event.changedTouches[0] : event;

    const newNode: Node = {
        type: "stepNode",
        id,
        data: { label: `Step ${id}` },
        position: screenToFlowPosition({x: clientX, y: clientY}),
        origin: [0.5, 0.0]
    };

    nodes = [...nodes, newNode];
    edges = [
        ...edges,
        {
            source: sourceNodeId,
            target: id,
            id: `${sourceNodeId}--${id}`,
        },
    ];
};

// svelte-ignore non_reactive_update
const handleExport = () => {
    const graphData = toObject();

    if (onExport) {
        onExport(graphData);
    } else {
        console.log("Export clicked:", graphData)
    }

    return graphData;
}


export { handleExport };
</script>

<div class="canvas">
    <SvelteFlow
        bind:nodes
        bind:edges
        { nodeTypes }
        { onExport }
        fitView
        onconnectend={handleConnectEnd}
        style="position: absolute;"
    >
        <Controls />
        <Background bgColor="#f5f5f5" variant={BackgroundVariant.Dots} />
        <MiniMap nodeStrokeWidth={3} />
        <Panel position="top-right">
            <button onclick={handleExport} class="panel-btn">
                <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#1f1f1f"><path d="M480-320 280-520l56-58 104 104v-326h80v326l104-104 56 58-200 200ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/></svg>
                Export
            </button>
            <button onclick={handleExport} class="panel-btn">
                <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#1f1f1f"><path d="M440-320v-326L336-542l-56-58 200-200 200 200-56 58-104-104v326h-80ZM240-160q-33 0-56.5-23.5T160-240v-120h80v120h480v-120h80v120q0 33-23.5 56.5T720-160H240Z"/></svg>
                Upload
            </button>
        </Panel>
    </SvelteFlow>
</div>

<style>
    .canvas {
        align-items: center;
        display: flex;
        width: 100%;
        height: 100%;
        justify-content: center;
    }

    .panel-btn {
        padding: 8px 16px;
        background: #f5f5f5;
        border: 1px solid #6a6e6e;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .panel-btn:hover {
        background: #dce0e3;
    }
</style>
