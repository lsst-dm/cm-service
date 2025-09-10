# CM Service Web UI v2
The CM Service Web UI is a [nicegui](https://nicegui.io)-based web ui prototype.
It operates exclusively via API calls to a CM Service server; no database access is necessary.

## Installation
This web ui is not presently built or deployed as part of the CM Service Phalanx application, though in future it may be.
This web ui may be run locally on a developer or pilot's laptop whenever the CM Service git repo is cloned and set up for development use (e.g., by use of `make init`).

The web ui package can be installed explicitly with `uv sync --all-packages`.

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
