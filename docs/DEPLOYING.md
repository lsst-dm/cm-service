# Deploying CM Service
Deploying CM Service (CM) requires a Phalanx-powered ArgoCD environment, which is a Kubernetes cluster or virtual cluster into which an application can be deployed.

## Prerequisites
Before a CM application can be deployed to an environment, ensure these prerequisites are met.

### Gafaelfawr
The target environment should have a gafaelfawr ingress configured. Usually this means a PostgreSQL database to support gaefaelfawr as well. The values file for the the *environment* should have:

```
applications:
  gafaelfawr: true
  postgres: true
```

> [!Note]
> Enabling gafaelfawr (and its database) for an environment requires an out-of-band action to generate and store secrets as well as bootstrapping the gafaelfawr database schema. Ensure that these actions are complete before deploying a new application with Phalanx.

### Database
Active and available PostgreSQL database. This can be the Phalanx-managed Postgres database in an environment, another k8s-deployed database in the same environment, an external infrastructure-managed database, or a cloud database. As long as the application can reach the database by name and successfully authenticate, any Postgres database can be used.

> [!Note]
> The only unsupported database configuration is a database managed by the same ArgoCD application as CM itself, because the database migration job occurs in the application pre-install hook.

#### Internal Database
Using the internal Phalanx database with CM Service is supported when the environment's `postgres` application has been configured to create a database and user for CM Service. In the environment values file for the `postgres` *application*, set:

```
cmservice_db:
  user: cmservice
  db: cmservice
```

> [!Note]
> Enabling this database and user in the `postgres` application requires an out-of-band secrets management action to generate new secrets and store them in Vault.

### Secrets
The CM Service consumes several secrets from the k8s application environment. These secrets must be available in the target phalanx environment before the service can successfully start and operate.

- Postgres. If the deployment uses a Phalanx-managed database, the secret is *generated* by the `postgres` application for the environment, and CM Service *copies* the secret for its own use.

    - Every CM Service deployment template needing database access should have the `DB__PASSWORD` environment variable set using the value of the postgres secret. For the internal phalanx database, this is the `internalDatabasePassword` key in the `cm-service` secret.

- Butler. The CM Service uses secrets to configure Butler registry authentication details. This secret is either a manually-managed secret in the `cm-service` application or a Vault secret managed by the application's Vault Secret Operator. The value of these secret should be a JSON string representation of an otherwise valid `db-auth.yaml` file commonly used for storing Butler registry authentication secrets. The `db-auth.yaml` is an array of objects with `url`, `username`, and `password` keys. This value is stored in the environment variable `LSST_DB_AUTH_CREDENTIALS` rather than a filesystem object.

- PanDA. The CM Service uses secrets to store PanDA authentication information, specifically an id-token and a refresh-token.

- AWS. The CM Service uses secrets to authenticate with S3-compatible Object Stores. There are two sets of secrets relevant to this authentication.

  - The AWS "default" profile is configured to use environment variables for its credentials source, so the appropriate secrets should be assigned to the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables.

  - Authentication values for other profiles are stored in a secret mounted as a file at `/etc/aws/credentials`.

## Dev / Staging Deployments
Development or staging builds are deployed to the USDF Kubernetes vcluster `usdf-cm-dev`.

Prior to deploying a new build using a prerelease tag, release tag, or ticket branch tag, it may be necessary to clear the database of all data so it can be migrated from scratch.

### Clearing the Database
After appropriately setting the Kubernetes context and namespace:

1. Scale down the daemon deployment using `kubectl scale deployment cm-service-daemon --replicas=0`.
1. Obtain a shell in an API server pod using `kubectl exec -it cm-service-server-<hash> -- bash`.
1. Within this shell, downgrade the database migration using `alembic downgrade base`.

> [!CAUTION]
> This operation unconditionally destroys the database contents and all objects.

## Object Store Access
CM Service may require configuration for one or more S3-compatible object stores. These may be used for Butler repo configuration files (although CM Service should not need to access Butler filestores) or for accessing external resources defined for a campaign or node via an `artifacts` manifest.

Standard `boto3` tooling configuration applies to CM Service, even if the object store provider is not AWS S3:

- `config` and `credentials` files. Maintaining access to multiple object stores depends on the "profile"-driven configurations supported by this pair of files. The `config` file should define for each profile any configuration detail as necessary -- especially the endpoint URL for the profile, and the `credentials` file should define for each profile the access key id and secret key pair that enables access. Multi-profile configuration is not possible via pure environment variable configuration, so the presence of these files is mandatory.

- Mandatory environment variables. The `AWS_CONFIG_FILE` and `AWS_SHARED_CREDENTIALS_FILE` variables should both be set, pointing to the appropriate files by absolute path. In addition to these, one or more `LSST_RESOURCES_S3_PROFILE_<profile>` variables should be set to the endpoint url for each profile. While this is redundant with the core `config` file, these variables are used by any `lsst.resources.ResourcePath` instances used by the application.

- Optional environment variables. Setting standard AWS-compatible environment variables, including `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` is optional and should apply only to a "default" profile, which is likely undefined for a given deployment of CM Service. Likewise, setting and endpoint with `AWS_ENDPOINT_URL_S3` is not mandatory.

## Butler Access
CM Service may access one or more Butler registries to satisfy dataset queries, but should not need any datastore access (i.e., CM Service does not acquire any Butler-managed data).

At startup, CM Service primes Butler objects for each Butler configured in the `DAF_BUTLER_REPOSITORIES` environment variable, which is a JSON string mapping of a repo name to a configuration file.

The instantation of each Butler may require access to the referenced configuration file by POSIX path or S3 URL.

In the case of an S3 URL, the file is fetched by the Butler using an `lsst.resources.ResourcePath`, so the profile named in the URL must have a matching configuration and credential (see "Object Store Access" above).

In the case of POSIX path, the exact path must be a mounted filesystem or PVC that provides access to the named file or directory.

In either case, the config file will define a database connection URL. This database must have a matching credential in the `LSST_DB_AUTH_CREDENTIALS` environment variable, which is the JSON string equivalent of a `db-auth.yaml` file.

## Supplying Secrets to Launched Jobs
Most payloads executed by CM Service are delivered to HTCondor to run in a `local` universe.
An environment firewall exists between the service's runtime environment and the environment inherited by the HTCondor job submission ("launcher").

Secrets are *not* set in this launcher environment, as it is expected that one or more processes may create plaintext dumps of the execution environment during payload execution, and this can expose secrets.

To the degree that launcher job payloads may require secrets usually provided by `aws-credentials.ini` and/or `db-auth.yaml`, service-specific instances of these files are located in the HTCondor user home directory and the launcher environment sets variables that point to these files.

> [!CAUTION]
> CM does not currently manage these secrets files, and out-of-band manipulation of these files may impact CM launcher behavior.
