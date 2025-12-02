<script lang="ts">
    import { Handle, Position, type NodeProps } from "@xyflow/svelte";

    let { id, data, isConnectable }: NodeProps = $props();
</script>

<div class="svelte-flow__node-default">
    <Handle type="source" position={Position.Bottom} {isConnectable} />

    <div>
    {id}
    </div>
</div>
