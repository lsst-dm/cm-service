# cm-service
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Flsst-dm%2Fcm-service%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

This is the Rubin Observatory data processing campaign management ReST service. `cm-service` is developed with
[FastAPI](https://fastapi.tiangolo.com) and [Safir](https://safir.lsst.io). Learn more at
https://cm-service.lsst.io.

## Developer Quick Start

You can build and run `cm-service` on any system which has Python 3.12 or greater, `uv`, `make`, and Docker w/ the
Docker Compose V2 CLI plugin (this includes, in particular, recent MacOS with Docker Desktop).  Proceed as
follows:

* Ensure `uv` is installed (via Homebrew (macOS), `pipx`, or a preferred alternative method).

  - You may run `make uv` to bootstrap uv in your environment.
  - Suggested: set `UV_PYTHON_PREFERENCE=only-managed` to prevent non-`uv` Pythons from being used.
  - USDF: set `UV_NATIVE_TLS=true` for compatibility with the Squid proxy.

* Install Python virtual environment, dependencies and activate pre-commit hooks with `make init`.

  - `uv` will automatically install any needed Python version.
  - Note: the `ctrl-bps-htcondor` plugin is not available on macOS and will not be installed on this platform.

* Ensure the virtual environment is activated before interacting with other make targets:

  - `source .venv/bin/activate`

* Spin up a debug instance of the service running in the foreground of the current shell with `make run`. This
  will launch a subsidiary Postgres instance locally in a Docker container via Docker Compose. The foreground
  debug service instance will log to stdout and will dynamically reload as you edit and save source files.

  * You may also choose to run both the service/worker and the database in Docker by running `docker compose --profile full up`;
    in particular this will exercise the Docker build process.

  * You may choose to (re)build the service container with `docker compose build [--no-cache] cmservice` to build, but not
    start, the service container (with `--no-cache` invalidating the build cache if needed).

* Access the monitoring web application at http://localhost:8080/web_app/campaigns/

* Exit your debug instance with `^C`.  The subsidiary Postgres container launched under Docker Compose will
  remain active, and will be re-used on any subsequent `make run`.

* Shut down the subsidiary Postgres container if/when desired with `docker compose down`.  Database state will
  be maintained in local Docker volumes and re-used on the next run.  If you wish to clear the database state
  volumes as well to start completely fresh, do `docker compose down -v`.

Additional developer conveniences:

* Browse the integrated online ReST API documentation while the service is running at
  http://localhost:8080/docs.

* Run the pytest test suite at any point with `make test`.  This will launch subsidiary containers if
  necessary via Docker Compose, or will make use of any that may already be running.  Tests are performed in
  their own Postgres schema, so as not interfere with debugging state in a running debug service instance.
  (You may run `docker compose down -v` to clean up completely between runs.)

* To run the playwright tests, add `--run-playwright` to the pytest arguments

* Run the pre-commit hooks to lint and reformat your code via `make lint`.

* Run the mypy static type hint checker with `make typing`.

* Connect the `psql` command line client directly to the subsidiary Postgres for direct database inspection
  or manipulation via `make psql`.

## Project Management

CM-Service is constructed as a collection of independent but inter-dependent *workspace* members.
Each workspace member has its own project directory inthe `packages/` directory.
Each workspace member project includes a `pyproject.toml` and `src/` and `tests/` directories.
Each member's `pyproject.toml` defines dependencies for the specific workspace project, which may include *other* workspace members.
As a convience, all `dev` group dependencies are specified in a single dependency group in the *root* project workspace.

* `uv add --project <project> <dependency>` will add a dependency to the `project`; `uv add --group dev ...` will mark it as
   a development dependency.

* `make update` will cause `uv` to upgrade all available dependencies within the constraints set for
  the dependency in any workspace `pyproject.toml` file.

* `uv run <cmd>` will execute `<cmd>` within the project environment, which is useful for cases where
  the virtual environment is not activated.

* `make clean` will remove the virtual environment and allow `make init` to create it from scratch. The
  lock file is not removed by this target.

* The lock file can be regenerated by removing (or renaming) the `uv.lock` file and running `make uv.lock` or
  the direct command `uv lock`.

* `uv` uses a global package cache for speed and efficiency; you manage this cache with `uv cache prune` or
  `uv cache clean` for the nuclear option.

* `uv build --all-packages` can be used to produce wheel files for all the workspace member packages, but this is generally not necessary to build the project or use its tools. No component of this project is published to pypi or other package registries, but it may be included in other projects if needed using standard Github URL dependency specifications.

### Typing
This project is governed by the `mypy` static type checker, either by calling `make typing` or by CI.
Other type checkers may be incidentally applied to the project, such as `pyright` (especially via the VS Code Python extention), but for the most part action is not taken to satisfy any type checker other than `mypy`.

Each workspace member project has a `py.typed` marker file indicating its typed status.
