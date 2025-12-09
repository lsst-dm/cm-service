<script lang="ts">
  import {
    Handle,
    Position,
    useSvelteFlow,
    type NodeProps,
  } from "@xyflow/svelte";

  let { id, data }: NodeProps = $props();
</script>

<div class="end-node">
  <div class="end-node-label">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="24px"
      viewBox="0 -960 960 960"
      width="24px"
      ><path
        d="M360-720h80v-80h-80v80Zm160 0v-80h80v80h-80ZM360-400v-80h80v80h-80Zm320-160v-80h80v80h-80Zm0 160v-80h80v80h-80Zm-160 0v-80h80v80h-80Zm160-320v-80h80v80h-80Zm-240 80v-80h80v80h-80ZM200-160v-640h80v80h80v80h-80v80h80v80h-80v320h-80Zm400-320v-80h80v80h-80Zm-160 0v-80h80v80h-80Zm-80-80v-80h80v80h-80Zm160 0v-80h80v80h-80Zm80-80v-80h80v80h-80Z"
      /></svg
    >
  </div>

  <Handle
    type="target"
    id="top"
    position={Position.Top}
    isConnectableStart={false}
  />
  <Handle
    type="target"
    id="left"
    position={Position.Left}
    isConnectableStart={false}
  />
</div>

<style>
  .end-node {
    background-color: var(--rubin-color-indigo-dark);
    border: 1px;
    border-color: var(--rubin-color-black-light);
    border-radius: 20px;
    padding: 5px 2px 0px 3px;
  }
  .end-node-label {
    svg {
      fill: var(--rubin-color-white-light);
    }
  }
</style>
