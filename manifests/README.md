> [!NOTE]
> FIXME: Remove all this with prejudice once we have cut over to using phalanx
> shared service for production...

Kustomize charts for standalone shared back-end Postgres at USDF.  `cd` to
`usdf-cm-dev` and `make deploy` to deploy, etc.

Will retrieve Postgres secrets from vault and populate as k8s secrets.  Requires
valid vault and kubectl credentials.
