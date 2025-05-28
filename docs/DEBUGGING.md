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

## Database
Direct connections to a CM Service database are generally not allowed or configured.
In cases where the database is hosted in a Kubernetes deployment, as when using a Phalanx database or a custom database, pod access or port-forwarding is usually sufficient for making an indirect connection.

### Requirements
Making a connection to a CM Service database requires at least the set of PosgreSQL client tools available via the `libpq` package (the availability of which is os-dependent, but `brew install libpq` is usually sufficient for macOS).
The use of a database IDE or visualizer is strongly encouraged; dBeaver is one such tool.

### Credentials
Database login credentials should not be shared or available outside the application context.
The deployment of CM Service does not establish "user" roles or accounts, so unless other efforts have been made in this regard, there is no set of credentials other than the secrets used by the application itself.

### Connecting

Basic database operations may be accomplished from a CM Service application pod.
In this sense, "basic" operations means those accomplished via application code (e.g., `alembic` migrations or the Python REPL) as the PostgreSQL client tools are not available in these pods.

More advanced database operations may be accomplished from a PostgreSQL pod directly, if the database is running in Kubernetes. Assuming the operator has effective Kubernetes permissions, a shell obtained via `kubectl` should grant access to the full suite of database client tools if they are available in the pod.

Port-forwarding is the best solution for operators who otherwise have access to credentials. Using `kubectl port-foward <pod-name> :5432` will provide a random `localhost` port forwarded to the database port in the running pod.
Subsequently, all IDE or CLI tools should be referred to this `localhost` port for database connections, which in all meaningful ways is equivalent to a direct connection.
