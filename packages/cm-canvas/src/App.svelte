<script lang="ts">
    import "@xyflow/svelte/dist/style.css";
    import { SvelteFlowProvider, type Node } from "@xyflow/svelte";
    import CmCanvas from "./CmCanvas.svelte";

    /* A set of defaultNodes for an otherwise empty canvas. Because a CM campaign
    always has a definite START and END, these are included. Although this canvas
    component does not perform graph validation, the CM server will not allow an
    invalid campaign graph to enter a running state.
    */
    const defaultNodes: Node[] = [
        {
            id: "START",
            type: "startNode",
            position: { x: 0, y: 0 },
            data: { label: "START" },
        },
        {
            id: "END",
            type: "endNode",
            position: { x: 100, y: 100 },
            data: { label: "END" },
        },
    ];

    /* A set of props to send to the Canvas component
    */
    let {
        nodes = defaultNodes,
        edges = [],
        ...restProps
    } = $props()

</script>

<SvelteFlowProvider>
    <CmCanvas {nodes} {edges} {...restProps} />
</SvelteFlowProvider>
