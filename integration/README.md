# Integration Testing
This directory contains resources for integration testing of CM Service configured to use an HTCondor launcher.

## Components

- `docker-compose.yaml`: A compose file that extends the base `docker-compose.yaml` by adding an HTCondor "mini" service.
- `integration-overrides.yaml`: Configuration extentions for the base `docker-compose.yaml` to enable its use with the integration stack.
- `script/`: A directory of utility and/or runtime scripts that enable or help orchestrate the integration test.
- `passwords.d`: a reusable `POOL` password file for HTCondor used as a signing key for ID tokens. *This is not a production key.*
- `tokens.d`: A directory of HTCondor ID tokens used by CM Service to authenticate during job Launches. These tokens are signed by the reusable `POOL` signing key. *These are not production tokens.*
- `butler.d`: A directory of items related to bootstrapping and running a Butler registry for integration testing.

## Secrets
The signing key and JWT tokens are shared secrets. These are not production keys or tokens, so it is not an error to commit them to VCS.

The signing key (`passwords.d/POOL`) is generated using `condor_store_cred add -c -p <PASSWORD> -f POOL`.

Each JWT token is then generated using the signing key with `condor_token_create -identity <user>@<host> -authz WRITE -authz READ -key POOL`.

## Scripts

- `rubin.py`. This is a mock multi-tool that generates specific side effects or exit codes depending on how it is called. This script is designed to be used with the HTCondor execution environment as a stand-in for any CLI or stack commands a job may invoke. This is done by symlinking the `rubin.py` script to any number of other file names like `bps`, `butler`, `setup`, `eups`, etc. This script is designed to work with Python 3.9, the system Python currently available in the HTCondor mini image, using the *standard library* only.

- `bootstrap.py`. This is a butler registry seed script that creates a new Butler repo and adds dimensions and datasets to the registry. This is not a filestore-backed butler but metadata-only `raw`s are added for two `day_obs`.

## Testing

The integration testing stack may be created by calling `docker compose --profile full up` from the `integration/` directory. Optionally, `docker compose down -v` and/or `docker compose build` may be useful to clean up or refresh the application artifacts.

The CM Web application is available at `localhost:18080`, where a campaign can be designed or imported for use as an end-to-end integration test (not tested: any tools mocked by `rubin.py`). Alternately, the CM Service API is available at `localhost:8080` for use with the CM CLI or an external instance of CM Web.

The integration test stack is meant to drive any running campaign from START to END without breakpoints (though these will be respected when encountered) or errors, so is useful for validating CM Service operations, group configurations, artifact rendering, and campaign graph evolution. It is not meant to model any particular use case, failure scenario, or provide a debugging interface.
