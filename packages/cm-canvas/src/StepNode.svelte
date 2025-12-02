<script lang="ts">
    import { Handle, Position, useSvelteFlow, type NodeProps } from "@xyflow/svelte";

    let { id, data }: NodeProps = $props();

    let { updateNodeData } = useSvelteFlow();
</script>

<div class="svelte-flow__node-default">
    <Handle type="target" position={Position.Top} />

    <div class="step-node-form-group">
    <input
        id="name"
        name="name"
        type="input"
        value="Step {id}"
        oninput={(e) => {updateNodeData(id, { name: e.target.value })}}
        class="step-node-form-field"
        required
    />
    <label for="name" class="step-node-form-label">Step Name</label>
    <input
        id="yaml"
        name="yaml"
        type="input"
        value={data.yaml}
        oninput={(e) => {updateNodeData(id, { text: e.target.value })}}
        class="step-node-form-field"
        required
    />
    <label for="yaml" class="step-node-form-label">Pipeline YAML</label>
    </div>

    <Handle type="source" position={Position.Bottom} />
</div>

<style>

    .step-node-form-group {
        font-family: "roboto", sans-serif;
        font-size: 1rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        position: relative;
        padding: 2px 0 0;
        margin-top: 2px;
        width: 100%;
    }

    .step-node-form-field {
        font-style: italic;
        font-size: 0.8rem;
        font-weight: lighter;
        width: 100%;
        border: 0;
        border-bottom: 2px solid #6a6e6e;
        outline: 0;
        color: #313333;
        padding: 3px 0;
        background: transparent;
    }

    .step-node-form-label {
        display: block;
        font-size: 0.5rem;
        color: #6a6e6e;
        font-weight: lighter;
        font-style: italic;
    }

    .step-node-form-field:focus {
        font-weight: heavier;
        font-style: normal;
        border-image: linear-gradient(to right, #00babc, #005684);
        border-image-slice: 1;
    }
</style>
