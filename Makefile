SHELL := /bin/bash
GIT_BRANCH := $(shell git branch --show-current)
PRERELEASE := $(shell if [[ $(GIT_BRANCH) =~ main ]]; then echo '--minor'; else echo '--prerelease --no-tag --no-commit'; fi)
PY_VENV := .venv/
UV_LOCKFILE := uv.lock

#------------------------------------------------------------------------------
# Default help target (thanks ChatGPT)
#------------------------------------------------------------------------------

help:
	@echo "Available targets:"
	@awk -F':' '/^[a-zA-Z0-9\._-]+:/ && !/^[ \t]*\.PHONY/ {print $$1}' $(MAKEFILE_LIST) | sort -u | column


#------------------------------------------------------------------------------
# DX: Use uv to bootstrap project
#------------------------------------------------------------------------------

$(UV_LOCKFILE):
	uv lock --build-isolation

$(PY_VENV): $(UV_LOCKFILE)
	uv sync --frozen

.PHONY: clean
clean:
	rm -rf $(PY_VENV)

.PHONY: update-deps
update-deps:
	uv lock --upgrade --build-isolation

.PHONY: init
init: $(PY_VENV)
	uv run playwright install
	uv run pre-commit install

.PHONY: update
update: update-deps init

#------------------------------------------------------------------------------
# Target to create a "release" that consists of an increment of the version
# patch level in the appropriate file, a git commit and a matching git tag when
# the branch is "tickets/*"; otherwise a prerelease version is created and no tag
# is made.
#------------------------------------------------------------------------------

.PHONY: release
release: export GIT_COMMIT_AUTHOR="$(shell git config user.name) <$(shell git config user.email)>"
release:
	uv run semantic-release version $(PRERELEASE) --no-push --no-vcs-release --skip-build --no-changelog

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
	psql postgresql://python3 -m lsst.cmservice.cli.server:${CM_DATABASE_PASSWORD}@localhost:${CM_DATABASE_PORT}/python3 -m lsst.cmservice.cli.server

.PHONY: test
test: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
test: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@localhost:${CM_DATABASE_PORT}/python3 -m lsst.cmservice.cli.server
test: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
test: export CM_DATABASE_SCHEMA=cm_service_test
test: run-compose
	python3 -m lsst.cmservice.cli.server init
	pytest -vvv --asyncio-mode=auto --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run
run: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@localhost:${CM_DATABASE_PORT}/python3 -m lsst.cmservice.cli.server
run: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
run: export CM_DATABASE_ECHO=true
run: run-compose
	python3 -m lsst.cmservice.cli.server init
	python3 -m lsst.cmservice.cli.server run

.PHONY: run-worker
run-worker: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run-worker: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@localhost:${CM_DATABASE_PORT}/python3 -m lsst.cmservice.cli.server
run-worker: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
run-worker: export CM_DATABASE_ECHO=true
run-worker: run-compose
	python3 -m lsst.cmservice.cli.server init
	python3 -m lsst.cmservice.daemon


#------------------------------------------------------------------------------
# Targets for developers to debug running against local sqlite.  Can be used on
# local machines or USDF dev nodes.
#------------------------------------------------------------------------------

.PHONY: test-sqlite
test-sqlite: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
test-sqlite:
	python3 -m lsst.cmservice.cli.server init
	pytest -vvv --asyncio-mode=auto --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run-sqlite
run-sqlite: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
run-sqlite: export CM_DATABASE_ECHO=true
run-sqlite:
	python3 -m lsst.cmservice.cli.server init
	python3 -m lsst.cmservice.cli.server run

.PHONY: run-worker-sqlite
run-worker-sqlite: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
run-worker-sqlite: export CM_DATABASE_ECHO=true
run-worker-sqlite:
	python3 -m lsst.cmservice.cli.server init
	python3 -m lsst.cmservice.daemon


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
psql-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
psql-usdf-dev: CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
psql-usdf-dev: ## Connect psql client to backend Postgres (shared USDF)
	psql postgresql://python3 -m lsst.cmservice.cli.server:${CM_DATABASE_PASSWORD}@${CM_DATABASE_HOST}:5432/python3 -m lsst.cmservice.cli.server

.PHONY: test-usdf-dev
test-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
test-usdf-dev: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@${CM_DATABASE_HOST}:5432/python3 -m lsst.cmservice.cli.server
test-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
test-usdf-dev: export CM_DATABASE_SCHEMA=cm_service_test
test-usdf-dev:
	pytest -vvv --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run-usdf-dev
run-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
run-usdf-dev: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@${CM_DATABASE_HOST}:5432/python3 -m lsst.cmservice.cli.server
run-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
run-usdf-dev: export CM_DATABASE_ECHO=true
run-usdf-dev:
	python3 -m lsst.cmservice.cli.server init
	python3 -m lsst.cmservice.cli.server run

.PHONY: run-worker-usdf-dev
run-worker-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
run-worker-usdf-dev: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@${CM_DATABASE_HOST}:5432/python3 -m lsst.cmservice.cli.server
run-worker-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n python3 -m lsst.cmservice.cli.server get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
run-worker-usdf-dev: export CM_DATABASE_ECHO=true
run-worker-usdf-dev:
	python3 -m lsst.cmservice.daemon

get-env-%: CM_DATABASE_HOST=$(shell kubectl --cluster=$* -n python3 -m lsst.cmservice.cli.server get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
get-env-%: export CM_DATABASE_URL=postgresql://python3 -m lsst.cmservice.cli.server@${CM_DATABASE_HOST}:5432/python3 -m lsst.cmservice.cli.server
get-env-%: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=$* -n python3 -m lsst.cmservice.cli.server get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
get-env-%: export CM_DATABASE_ECHO=true
get-env-%:
	rm -f .env.$*
	echo CM_DATABASE_URL=$${CM_DATABASE_URL} > .env.$*
	echo CM_DATABASE_ECHO=$${CM_DATABASE_ECHO} >> .env.$*
	echo CM_DATABASE_PASSWORD=$${CM_DATABASE_PASSWORD} >> .env.$*
