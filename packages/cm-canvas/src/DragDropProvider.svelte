<!-- This context provider allows sharing draggable Nodes between the Sidebar and main Canvas
using Svelte's Context API. When the drag starts, the node type is stored in context
and any child component can access this via `useDragDrop`. On drop, the node type
is retrieved from the context. -->

<script module>
  import { getContext } from "svelte";
  export const useDragDrop = () => {
    return getContext("dragdrop") as { current: string | null };
  };
</script>

<script lang="ts">
  import { onDestroy, setContext, type Snippet } from "svelte";
  let { children }: { children: Snippet } = $props();
  let dragDropType = $state(null);

  setContext("dragdrop", {
    set current(value) {
      dragDropType = value;
    },
    get current() {
      return dragDropType;
    },
  });

  onDestroy(() => {
    dragDropType.set(null);
  });
</script>

{@render children()}
