# CM Canvas

The Canvas is a Svelte Flow component that is designed to allow the easy and visual creation and editing of a Campaign graph on a reactive canvas. The component is built as an Immediately Invoked Function Expression (IIFE).

## Dev Setup

To work on the Canvas, you will be using Svelte 5, Svelte Flow, and Typescript along with Vite and NPM.

To set up the dev environment, you must have `npm` and `make` installed and available. This is best accomplished by installing NodeJS v24.

Basic setup is performed using the `Makefile`:

```
make rebuild
```

; or:

```
npm install
npm run build
```

## Conventions

This component uses Svelte, which combines script, DOM, and style details in a single `.svelte` file for each part of the component.

This project uses `prettier` to format files in the project.

This component should be developed as a TypeScript project.

## Dev Test

The canvas tool can be run in a dev mode that supports hotloading and a local web server for testing or debugging simple operations; this mode is not integrated with the cm web tool at large. When using the canvas IIFE in another project as an embedded component, there is no `node` runtime dependency.

This test mode uses the `index.html` and `dev.js` files to mount the Svelte-Flow component in a div named "app" on an otherwise unremarkable index page.

```
npm run dev
```

## Build

The canvas tool is compiled to an IIFE module and accompanying CSS file with the vite packaging utility.

```
npm run build
```

The resulting dist artifacts must be made available to the cm web tool by copying them to the `static/` directory in the web tool source tree, which is performed automatically by the `make dist` target.

## Integration

This canvas component is integrated with CM Web via the inclusion of the compiled IIFE and CSS bundles. The script should be run to mount the component on a named div as expected by the `index.js` file, which is the "entrypoint" of the component.

For NiceGUI, a page can be made to include the bundles via header tags, and the script mounted to a div like so:

```
from nicegui import ui

ui.add_head_html("""<script src="/static/cm-canvas-bundle.iife.js"></script>""")

ui.element("div").classes("w-full h-full").props('id="flow-container"')
ui.run_javascript("""
    window.flowInstance = initializeFlow('flow-container', {});
""")
```

### Properties

The `initializeFlow` function in the IIFE component passes a set of properties to the Canvas:

- `nodes`: An array of Node objects. These objects should conform to the Svelte Flow implementation of a Node. A default set of nodes (i.e., "START" and "END") will be used when this property is null or missing.
- `edges`: An array of Edge objects. Again, these are Svelte Flow Edges. This defaults to an empty array (i.e., no Nodes are connected) when this property is null or missing.
- `onClick`: A Javascript function definition to be used with the "Edit" button available on Step on the Canvas.

### Example Node
```
{
    "id": "unique id",
    "type": "step | start | end",
    "data": { "name": "node name" },
    "position": { "x": 0, "y": 0 }
}
```

Note the "position" of a Node doesn't really matter when initializing the canvas, because the component will call one of the layout functions automatically in an "onMount" lifecycle callback.

### Example Edge
```
{
    "id": "source--target",
    "source": "id",
    "target": "id"
}
```

Note that the "source" and "target" keys need the unique IDs of the subject Nodes, not their names. The handle positions of an Edge will be manipulated automatically by the Canvas component when one of the layout functions is called. Generally, this means that "Horizontal" layout connects edges from left-to-right, and "Vertical" connects them bottom-to-top. It is not necessary to specify handle positions when supplying edges in the initializer.

## Usage

The Canvas is meant for campaign designers to layout a Campaign using nodes and edges. Only basic campaign graph structure is configurable with this Canvas; additional configurations are made through other CM interfaces. This component does not perform graph validation.

A canvas by default includes "START" and "END" nodes. New _Steps_ can be added by dragging an edge out of an existing node and ending on a blank part of the canvas where the new Step should be placed.

When hovering over a Node on the Canvas, four handles appear; the top and left handles are target/destination handles and new connections cannot be pulled out of these. The bottom and right handles are source handles and new connections can be pulled out of these. A new connection can be dropped on a blank area of the Canvas to create a new Step node, or connected to the top or left handle of an existing node -- a valid connection will be highlighted in green.

A new Step node can be given a _Name_. A Step node also has an "Edit" button which performs the action configured by the `onClick` property passed into the component's initialization. By convention, the CM Web UI causes this button to emit a Javascript event which in turn allows an Edit dialog to appear.

While Step names are arbitrary and can be changed, they are given an initial name based on the order the Node was added to the Canvas, starting with "Step 1".

Note that this canvas component does not itself save or fully configure campaigns or steps: it is only through one of the action buttons that the configured graph is sent as data to the CM Web ui for additional configuration and setup.

The canvas also includes two panel buttons that are self-contained (i.e., they do not emit events for external handling). These are auto-layout buttons to redesign the current graph in either a vertical or horizontal layout. Larger graphs can be complicated to read; these layout buttons help designers keep the graph clean.

## Events
The Canvas component has the following event listeners by default:

- `canvasExport`: Causes the current graph on the canvas to be serialized and returned as data with an answering `canvasExported` event. The current positions of the nodes are not part of the export: only the shape of the graph and core identity of the nodes (i.e., their unique ID and Name values) are exported. No other state for a Node is ever stored or saved by the Canvas.
