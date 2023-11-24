default:

.secrets:
	mkdir -p -m 700 .secrets

.secrets/pg: .secrets
	mkdir -p -m 700 .secrets/pg

.secrets/redis: .secrets
	mkdir -p -m 700 .secrets/redis

.PHONY: fetch-vault-secrets
fetch-vault-secrets: export VAULT_ADDR=https://vault.slac.stanford.edu
fetch-vault-secrets: .secrets/pg .secrets/redis
	vault kv get -mount=secret -field=username rubin/usdf-cm-dev/postgres > .secrets/pg/username
	vault kv get -mount=secret -field=password rubin/usdf-cm-dev/postgres > .secrets/pg/password
	vault kv get -mount=secret -field=password rubin/usdf-cm-dev/redis > .secrets/redis/password

.PHONY: remove-vault-secrets
remove-vault-secrets:
	rm -rf .secrets

.PHONY: deploy
deploy:
	fetch-vault-secrets
	kubectl apply -k .
	remove-vault-secrets

.PHONY: undeploy
undeploy:
	kubectl delete -f .
