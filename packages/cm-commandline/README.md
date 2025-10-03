# CM Service Command Line Interface v2
The CM Service CLI is a [typer](https://typer.tiangolo.com)-based commandline prototype.
It operates exclusively via API calls to a CM Service server; no database access is necessary.

## Installation
This CLI is not presently built or deployed as part of the CM Service Phalanx application, though in future it may be.
This CLI may be run locally on a developer or pilot's laptop whenever the CM Service git repo is cloned and set up for development use (e.g., by use of `make init`).

The CLI package can be installed explicitly with `uv sync --all-packages`.

### Alternate Tool Installation
The CLI package may also be installed as a `uv`-managed tool without necessarily cloning and setting up the entire `cm-service` repository:

`uv tool install -p 3.12 git+https://github.com/lsst-dm/cm-service#subdirectory=packages/cm-commandline`

(You can target a specific branch for the installation by including `@<branchname>` just prior to `#subdirectory`.)

To subsequently upgrade or uninstall the tool, use its package name:

```
> uv tool upgrade lsst-cmservice-commandline
> uv tool uninstall lsst-cmservice-commandline
```

## Configuration
The `lsst.cmservice.commandline.settings` module defines the available configuration settings for the CLI.
The most important of these are the `CM_ENDPOINT` and `CM_TOKEN` environment variables.

- Set `CM_ENDPOINT` to the url of a CM Service server endpoint. This url should include the path at which the server application is mounted but not the API version. Example: `export CM_ENDPOINT=http://localhost:8080/cm-service`.
- Set `CM_TOKEN` to the secret authentication token you use to access CM Service through the Gafaelfawr ingress.

The CLI automatically loads a `dotenv` file located at `~/.cm-client` and uses the same environment variable names
as the CM Service Web UI.

You may install shell completion for the CM CLI with `cm --install-completion` but note that this may not work except when using `cm` in an activated virtual environment, i.e., completion may not work with `uv run cm ...`.

## Launching
Once installed, the commandline tool is available in the CM Service virtual environment with the executive name `cm` and can be invoked with `uv run cm ...` or if the virtual environment is *activated*, with `cm ...` directly.

Help for the CLI and its subcommands is available with the `--help` argument. The available subcommands are summarized here.

| subcommand | purpose |
| ---------- | ------- |
| loader     | loads YAML files containing manifests into the CM Service Application. |
| campaigns  | lists available campaigns and their details. |
| manifests  | lists available manifests and their details. |

### Global Options
You may see available global options when invoking `cm --help`. Each option has an associated environment variable.
