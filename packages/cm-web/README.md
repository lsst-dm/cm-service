# CM Service Web UI v2
The CM Service Web UI is a [nicegui](https://nicegui.io)-based web ui prototype.
It operates exclusively via API calls to a CM Service server; no database access is necessary.

## Installation
This web ui is not presently built or deployed as part of the CM Service Phalanx application, though in future it may be.
This web ui may be run locally on a developer or pilot's laptop whenever the CM Service git repo is cloned and set up for development use (e.g., by use of `make init`).

The web ui package can be installed explicitly with `uv sync --all-packages`.

### Dependencies
While this web ui package does not use Node, it does use a separate Svelte Flow component that must be built and supplied to this package via the `static/` directory. Building this component does require `node` and `npm`, modern versions of which can be installed in the usual way.

The most direct way to build and copy this Flow componet is to run `make packages` from the project root (not this directory). This make target performs the equivalent of `cd packages/cm-canvas && make rebuild`.

## Configuration
The `lsst.cmservice.web.settings` module defines the available configuration settings for the web ui.
The most important of these are the `CM_ENDPOINT` and `CM_TOKEN` environment variables.

- Set `CM_ENDPOINT` to the url of a CM Service server endpoint. This url should include the path at which the server application is mounted but not the API version. Example: `export CM_ENDPOINT=http://localhost:8080/cm-service`.
- Set `CM_TOKEN` to the secret authentication token you use to access CM Service through the Gafaelfawr ingress.

The web ui automatically loads a `dotenv` file located at `~/.cm-client` and uses the same environment variable names
as the CM Service CLI.

## Launching
The web ui can be started by running `make run-web` or `uv run web` from the workspace (repository) root.

The web ui can be started via the VS Code Debugger with the help of the following configuration, which can be added to your `launch.json` file. Note the use of a specific `envFile` directive; this can be omitted if your `~/.cm-client` is sufficient or changed to refer to a file of your choosing.

```
{
    "name": "Python Debugger: CM Web",
    "type": "debugpy",
    "request": "launch",
    "cwd": "${workspaceFolder}/packages/cm-web/src",
    "module": "lsst.cmservice.web.libexec.go",
    "args": ["-Xfrozen_modules=off"],
    "envFile": "${workspaceFolder}/.env"
},
```

## Static Content
The web ui uses a directory for static content. The primary contents of this directory are images (such as `favicon.png`) and additional script files, CSS files, etc.

By default, the web ui uses an embedded static directory that is part of the package. This is the `src/lsst/cmservice/web/static` directory relative to the package root. A different static directory may be used by setting the `CM_STATIC_CONTENT_DIR` environment variable to its location.

Note that the CM Canvas Svelte Flow component must be added to this static directory. When this component is built for distribution, a single script file is generated containing both the component's minified script code and its styling/CSS information. By default, the `make dist` target for the cm-canvas package will copy the file to the embedded static directory mentioned above unless the `CM_STATIC_CONTENT_DIR` environment variable is set, in which case the script will be copied to that location instead.
