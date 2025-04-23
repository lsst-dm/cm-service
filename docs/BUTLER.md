# CM Service and Butler
The CM Service uses a Butler at two levels: for its own use and for the use of batch jobs it submits.

## First-Party Butlers
CM Service uses Butlers to solve data queries, such as those used to determine group composition and splitting characteristics. CM Service also uses Butlers to assemble input collections and to chain output collections.

To provide Butler services for these first-party operations, CM Service uses a Butler Factory, which provides the following functionality:

- Instantiated and pre-cached Butler instances created on application startup.
- A caching mechanism to provide Butler clone instances to factory callers.
- Cloned Butler instances may be collection-constrained.

From this factory, CM Service will obtain a short-lived Butler clone for performing first-party butler operations.
Where these operations are synchronous and the CM event loop should not be blocked, Butler methods are executed on a threadpool or delegated to a FastAPI/starlette BackgroundTask.

The CM Service establishes a Butler factory at startup so that any blocking IO involved with the instantiation of Butlers is front-loaded.
CM Service uses some configuration details to determine the set of Butlers that the factory should support:

- The environment variable `DAF_BUTLER_REPOSITORIES` is used to construct an instance of `lsst.daf.butler.ButlerRepoIndex` for the service instance.
- The Butler registry authentication information must be available as a JSON string serialized to the `LSST_DB_AUTH_CREDENTIALS` environment variable, which is consumed by `lsst.util.db_auth.DbAuth` as its `authList`; CM Service does not support reading a DbAuth credential set from a file, as this requires file permissions incompatible with Kubernetes secrets mounted as volumes while also using a nonroot user in the container.

The contents of the `DAF_BUTLER_REPOSITORIES` environment variable is a JSON string that represents a mapping of Butler repo names to their associated configuration files.

<details>
<summary>Example Repository Index JSON object</summary>

```json
{
  "/repo/main": "/sdf/group/rubin/repo/main/butler.yaml",
  "/repo/main+sasquatch_dev": "/sdf/group/rubin/repo/main/butler+sasquatch_dev.yaml"
}
```

</details>

## Second-Party Butlers
When CM Service submits a batch job to run on a WMS, chances are high that the operations within that batch job will have to access a Butler for file IO.

The configuration parameter `config.butler.repository_index` is used to identify a Butler repository index file *relative to the WMS batch environment* that will be implicitly used by batch operations. This repository index file is expected to provide and resolve the correct Butler repository detail for a batch job that has been configured to use a Butler repository by its label.

The value of this configuration parameter is assigned to the environment variable `DAF_BUTLER_REPOSITORY_INDEX` in an environment specific to the batch submission operation, from which it is expected to be consumed by the appropriate `lsst.daf_butler` mechanisms when needed.

Authentication secrets for second-party Butlers are provided to batch jobs via `PGPASSFILE` and `PGUSER` environment variables, which are variables used by the `libpq` PostgreSQL client library as standard sources when no superceding sources are available.

The `PGUSER` variable is populated by the CM Service configuration parameter `config.butler.default_username`.
The `PGPASSFILE` value is constructed using the `config.htcondor.remote_user_home` configuration parameter and the fixed value `.lsst/postgres-credentials.txt`. This file is expected to be in a standard PostgreSQL password file format and have appropriate file mode permissions (i.e., not group- or world-accessible) as required by `libpq`.

> [!NOTE]
> This approach is suboptimal and delegates too many assumptions to the eventual batch submission context, especially the presence of specific files in specific locations. The batch submission context should be more or less completely controlled by the submitting service, including the creation of a specific short-lived `PGPASSFILE` with contents provided by the service's own understanding of the Butler repository. This assumes that the service will not submit a job that depends on a Butler which the service does not itself understand.

> [!NOTE]
> Secrets for second-party Butlers may also be provided via an environment variable. By setting `LSST_DB_AUTH_CREDENTIALS` with the JSON string representation of a `db-auth.yaml` file, all dependencies on presumed filesystem objects in the submission environment are resolved.
