<script lang="ts">
  import {
    Handle,
    Position,
    useSvelteFlow,
    type NodeProps,
  } from "@xyflow/svelte";

  let { id, data }: NodeProps = $props();

  let { updateNodeData } = useSvelteFlow();

  // svelte-ignore non_reactive_update
  const handleClick = () => {
    if (data.handleClick) {
      data.handleClick(id);
    } else {
      alert(`Default click handler: ${id}`);
    }
  };
</script>

<div class="svelte-flow__node-default">
  <Handle
    type="target"
    id="left"
    position={Position.Left}
    isConnectableStart={false}
  />
  <Handle
    type="target"
    id="top"
    position={Position.Top}
    isConnectableStart={false}
  />

  <div class="step-node-form-group">
    <input
      id="name"
      name="name"
      type="input"
      value="{data.name}"
      oninput={(e) => {
        updateNodeData(id, { name: e.target.value });
      }}
      class="step-node-form-field"
      required
    />
    <button id="edit" title="edit" onclick={handleClick} class="edit-btn">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="16px"
        viewBox="0 -960 960 960"
        width="16px"
        ><path
          d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h357l-80 80H200v560h560v-278l80-80v358q0 33-23.5 56.5T760-120H200Zm280-360ZM360-360v-170l367-367q12-12 27-18t30-6q16 0 30.5 6t26.5 18l56 57q11 12 17 26.5t6 29.5q0 15-5.5 29.5T897-728L530-360H360Zm481-424-56-56 56 56ZM440-440h56l232-232-28-28-29-28-231 231v57Zm260-260-29-28 29 28 28 28-28-28Z"
        /></svg
      >
    </button>
  </div>

  <Handle type="source" id="right" position={Position.Right} />
  <Handle type="source" id="bottom" position={Position.Bottom} />
</div>

<style>
  .step-node-form-group {
    font-family: "roboto", sans-serif;
    font-size: 1rem;
    display: inline-block;
    position: relative;
    padding: 2px 0 0;
    margin-top: 2px;
    width: 100%;
  }

  .step-node-form-field {
    font-style: italic;
    font-size: 0.8rem;
    font-weight: lighter;
    width: 75%;
    border: 0;
    border-bottom: 2px solid var(--rubin-color-grey-light);
    outline: 0;
    color: var(--rubin-color-black-light);
    padding: 3px 0;
    background: transparent;
  }

  .step-node-form-field:focus {
    font-weight: heavier;
    font-style: normal;
    color: var(--rubin-color-indigo-dark);
    border-image: linear-gradient(
      to right,
      var(--rubin-color-blue-light),
      var(--rubin-color-blue-dark)
    );
    border-image-slice: 1;
  }

  .edit-btn {
    border-radius: calc(infinity * 1px);
    border: none;
    padding: 3px;
    background-color: var(--rubin-color-indigo-dark);
    color: var(--rubin-color-white-dark);
    svg {
      fill: var(--rubin-color-white-dark);
    }
  }

  .edit-btn:hover {
    background-color: var(--rubin-color-indigo-light);
    color: var(--rubin-color-white-light);
    svg {
      fill: var(--rubin-color-white-light);
    }
  }
</style>
