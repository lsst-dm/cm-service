<script lang="ts">
    import { Handle, Position, useSvelteFlow, type NodeProps } from "@xyflow/svelte";

    let { id, data, isConnectable }: NodeProps = $props();
</script>

<div class="svelte-flow__node-default">
    <div>
    {id}
    </div>

    <Handle type="target" position={Position.Top} {isConnectable} />
</div>
