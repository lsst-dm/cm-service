# CM Canvas
The Canvas is a Svelte Flow component that is designed to allow the easy and visual creation and editing of a Campaign graph on a reactive canvas. The component is built as an Immediately Invoked Function Expression (IIFE).

## Dev Setup
To work on the Canvas, you will be using Svelte 5, Svelte Flow, and Typescript along with Vite and NPM.

To set up the dev environment, you must have `npm` and `make` installed and available.

Basic setup is performed using the `Makefile`:

```
make rebuild
```

; or:

```
npm install
npm run build
```

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

The resulting dist artifacts must be made available to the cm web tool by copying them to the `static/` directory in the web tool source tree.

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
- `onExport`: A Javascript function definition to be used with the "Export" button on the Canvas. The component includes a default function that dumps the graph objects to the Javascript Console.

## Usage

The Canvas is meant for campaign designers to layout a Campaign using nodes and edges. Only basic campaign graph structure is configurable with this Canvas; additional configurations are made through other CM interfaces. This component does not perform graph validation.

Assuming that a canvas includes the default "START" and "END" nodes, *Steps* can be added by dragging an edge out of an existing node and ending on a blank part of the canvas where the new Step should be placed.

A new Step node can be given a *Name* and a *Pipeline YAML*, each of which appear as input controls on the Node when placed on the Canvas. Both are simple string values, and are not validated.

While Step names are arbitrary and can be changed, they are given an initial name based on the order the Node was added to the Canvas, starting with "Step 1".

A Pipeline YAML is meant to express the full "path" to a step definition for the Step's configuration to inherit. An example of a Pipeline YAML is `${DRP_PIPE_DIR}/pipelines/LSSTCam/nightly-validation.yaml#stage3-coadd`.

Note that this canvas component does not itself save or fully configure campaigns or steps: it is only through one of the action buttons that the configured graph is sent as data to the CM Web ui for additional configuration and setup.
