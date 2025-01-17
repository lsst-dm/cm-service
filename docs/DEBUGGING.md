# Debugging

## VSCode

When using VSCode, you can use the debugger built into the Python extension to start an instance of the service
in a debug context by creating a `.vscode/launch.json` file in the Workspace. This configuration file
tells VSCode how to start an application for debugging, after which VSCode's breakpoints and other debug tools
are available.

This example `launch.json` file illustrates the launch of a debuggable CM Service and Daemon instances using `usdf-cm-dev`
resources:

```
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug: CM-Service [usdf-cm-dev]",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "--port", "8080", "--reload",
        "lsst.cmservice.main:app"
      ],
      "envFile": "${workspaceFolder}/.env.usdf-cm-dev"
    },
    {
      "name": "Debug: User Daemon [usdf-cm-dev]",
      "type": "debugpy",
      "request": "launch",
      "module": "lsst.cmservice.cli.client",
      "args": ["queue", "daemon", "--row_id", "${input:rowID}"],
      "envFile": "${workspaceFolder}/.env.usdf-cm-dev"
    },
    {
      "name": "Debug: System Daemon [usdf-cm-dev]",
      "type": "debugpy",
      "request": "launch",
      "module": "lsst.cmservice.daemon",
      "envFile": "${workspaceFolder}/.env.usdf-cm-dev"
    }
  ],
  "inputs": [
    {
      "id": "rowID",
      "description": "A Campaign Row ID for the debug client queue",
      "type": "promptString",
      "default": "1"
    }
  ]
}
```

Note that this configuration references an `envFile`; there is a `make` target for generating
`.env` files that can be consumed by VSCode debug configurations: `make get-env-<k8s cluster>`
(e.g., `make get-env-usdf-cm-dev` will produce a file `.env.usdf-cm-dev` with environment variables
set to values appropriate for services running in the named Kubernetes cluster). Otherwise, you may
create a custom `.env` file and reference it from Launch Configuration instead.

The debug Daemon is launched using a prompted value for the `--row_id` parameter, which will cause
VSCode to open a prompt for this input.
