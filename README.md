# cm-service

This is the Rubin Observatory data processing campaign management ReST service. `cm-service` is developed with
[FastAPI](https://fastapi.tiangolo.com) and [Safir](https://safir.lsst.io). Learn more at
https://cm-service.lsst.io.

## Developer Quick Start

You can build and run `cm-service` on any system which has Python 3.10 or greater, `make`, and Docker w/ the
Docker Compose V2 CLI plugin (this includes, in particular, recent MacOS with Docker Desktop).  Proceed as
follows:

* Establish and activate a Python 3.10 environment (e.g. with `conda create ...` or `python3 -m venv ...`).

* Install Python dependencies and activate pre-commit hooks with `make init`.

* Spin up a debug instance of the service running in the foreground of the current shell with `make run`. This
  will launch a subsidiary Postgres instance locally in a Docker container via Docker Compose. The foreground
  debug service instance will log to stdout and will dynamically reload as you edit and save source files.

* Access the monitoring web application at http://localhost:8080/web_app/campaigns/

* Exit your debug instance with `^C`.  The subsidiary Postgres container launched under Docker Compose will
  remain active, and will be re-used on any subsequent `make run`.

* Shut down the subsidiary Postgres container if/when desired with `docker compose down`.  Database state will
  be maintained in local Docker volumes and re-used on the next run.  If you wish to clear the database state
  volumes as well to start completely fresh, do `docker compose down -v`.

Additional developer conveniences:

* Browse the integrated online ReST API documentation while the service is running at
  http://localhost:8080/cm-service/v1/docs.

* Run the pytest test suite at any point with `make test`.  This will launch subsidiary containers if
  necessary via Docker Compose, or will make use of any that may already be running.  Tests are performed in
  their own Postgres schema, so as not interfere with debugging state in a running debug service instance.

* To run the playwright tests, add `--run-playwright` to the pytest arguments

* Run the pre-commit hooks to lint and reformat your code via `make lint`.

* Run the mypy static type hint checker with `make typing`.

* Connect the `psql` command line client directly to the subsidiary Postgres for direct database inspection
  or manipulation via `make psql`.
