#------------------------------------------------------------------------------
# Default help target (thanks ChatGPT)
#------------------------------------------------------------------------------

help:
	@echo "Available targets:"
	@awk -F':' '/^[a-zA-Z0-9\._-]+:/ && !/^[ \t]*\.PHONY/ {print $$1}' $(MAKEFILE_LIST) | sort -u | column


#------------------------------------------------------------------------------
# The usual dependency/environment management targets for Safir...
#------------------------------------------------------------------------------

.PHONY: update-deps
update-deps:
	pip install --upgrade pip-tools pip setuptools
	pip-compile --upgrade --build-isolation --generate-hashes --output-file requirements/main.txt requirements/main.in
	pip-compile --upgrade --build-isolation --generate-hashes --output-file requirements/dev.txt requirements/dev.in

# Useful for testing against a Git version of Safir.
.PHONY: update-deps-no-hashes
update-deps-no-hashes:
	pip install --upgrade pip-tools pip setuptools
	pip-compile --upgrade --build-isolation --allow-unsafe --output-file requirements/main.txt requirements/main.in
	pip-compile --upgrade --build-isolation --allow-unsafe --output-file requirements/dev.txt requirements/dev.in

.PHONY: init
init:
	pip install --editable .
	pip install --upgrade -r requirements/main.txt -r requirements/dev.txt
	playwright install
	pip install --upgrade pre-commit
	pre-commit install

.PHONY: update
update: update-deps init


#------------------------------------------------------------------------------
# Convenience targets to run pre-commit hooks ("lint") and mypy ("typing")
#------------------------------------------------------------------------------

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: typing
typing:
	mypy src tests


#------------------------------------------------------------------------------
# Targets for develpers to debug against a local Postgres run under docker
# compose. Can be used on local machines and in github CI, but not on USDF dev
# nodes since we can't run docker there.
#------------------------------------------------------------------------------

.PHONY: run-compose
run-compose:
	docker compose up --wait

.PHONY: psql
psql: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
psql: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
psql: run-compose
	psql postgresql://cm-service:${CM_DATABASE_PASSWORD}@localhost:${CM_DATABASE_PORT}/cm-service

.PHONY: test
test: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
test: export CM_DATABASE_URL=postgresql://cm-service@localhost:${CM_DATABASE_PORT}/cm-service
test: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
test: export CM_DATABASE_SCHEMA=cm_service_test
test: run-compose
	cm-service init
	pytest -vvv --asyncio-mode=auto --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run
run: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run: export CM_DATABASE_URL=postgresql://cm-service@localhost:${CM_DATABASE_PORT}/cm-service
run: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
run: export CM_DATABASE_ECHO=true
run: run-compose
	cm-service init
	cm-service run

.PHONY: run-worker
run-worker: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run-worker: export CM_DATABASE_URL=postgresql://cm-service@localhost:${CM_DATABASE_PORT}/cm-service
run-worker: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
run-worker: export CM_DATABASE_ECHO=true
run-worker: run-compose
	cm-service init
	cm-worker

#------------------------------------------------------------------------------
# Targets for develpers to debug running against local sqlite.  Can be used on
# local machines or USDF dev nodes. FIXME: This should probably be the norm for
# development/debug, but the pytest suite does not yet run correctly against
# sqlite...
#------------------------------------------------------------------------------

.PHONY: test-sqlite
test-sqlite: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
test-sqlite:
	cm-service init
	pytest -vvv --asyncio-mode=auto --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run-sqlite
run-sqlite: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
run-sqlite: export CM_DATABASE_ECHO=true
run-sqlite:
	cm-service init
	cm-service run

.PHONY: run-worker-sqlite
run-worker-sqlite: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
run-worker-sqlite: export CM_DATABASE_ECHO=true
run-worker-sqlite:
	cm-service init
	cm-worker


#------------------------------------------------------------------------------
# Targets for running per-developer service instances on USDF Rubin dev nodes,
# using a single shared backend cnpg Postgres in the usdf-cm-dev k8s vcluster.
# Currently used by most devs for development/debug, and also by pilots for
# production runs.
#
# FIXME: TO BE DEPRECATED as soon as we can reliably use shared phalanx service
# for production and sqlite for development/debug.
#------------------------------------------------------------------------------

.PHONY: psql-usdf-dev
psql-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
psql-usdf-dev: CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
psql-usdf-dev: ## Connect psql client to backend Postgres (shared USDF)
	psql postgresql://cm-service:${CM_DATABASE_PASSWORD}@${CM_DATABASE_HOST}:5432/cm-service

.PHONY: test-usdf-dev
test-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
test-usdf-dev: export CM_DATABASE_URL=postgresql://cm-service@${CM_DATABASE_HOST}:5432/cm-service
test-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
test-usdf-dev: export CM_DATABASE_SCHEMA=cm_service_test
test-usdf-dev:
	pytest -vvv --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run-usdf-dev
run-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
run-usdf-dev: export CM_DATABASE_URL=postgresql://cm-service@${CM_DATABASE_HOST}:5432/cm-service
run-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
run-usdf-dev: export CM_DATABASE_ECHO=true
run-usdf-dev:
	cm-service init
	cm-service run

.PHONY: run-worker-usdf-dev
run-worker-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
run-worker-usdf-dev: export CM_DATABASE_URL=postgresql://cm-service@${CM_DATABASE_HOST}:5432/cm-service
run-worker-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
run-worker-usdf-dev: export CM_DATABASE_ECHO=true
run-worker-usdf-dev:
	cm-worker
