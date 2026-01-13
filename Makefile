SHELL := /bin/bash
GIT_BRANCH := $(shell git branch --show-current)
PY_VENV := .venv/
UV_LOCKFILE := uv.lock
WEB_CANVAS_STEM := cm-canvas-bundle
WEB_PACKAGE_ROOT := packages/cm-web/

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
	uv sync --frozen --all-packages

.PHONY: clean
clean:
	rm -rf $(PY_VENV)
	rm -f test_cm.db
	rm -rf ./output
	find src -type d -name '__pycache__' | xargs rm -rf
	find tests -type d -name '__pycache__' | xargs rm -rf

.PHONY: update-deps
update-deps:
	uv lock --upgrade --build-isolation

.PHONY: init
init: $(PY_VENV)
	uv run playwright install
	uv run pre-commit install

.PHONY: update
update: update-deps init

.PHONY: build
build: export BUILDKIT_PROGRESS=plain
build: export COMPOSE_BAKE=true
build:
	docker compose build cmservice
	docker compose build cmworker

.PHONY: uv
uv:
	script/bootstrap_uv


#------------------------------------------------------------------------------
# Target to create a "release" that consists of an increment of the version
# patch level in the appropriate file, a git commit and a matching git tag on
# the "main" trunk; else a prerelease version is created and no tag is created.
#------------------------------------------------------------------------------

.PHONY: release
release: export GIT_COMMIT_AUTHOR="$(shell git config user.name) <$(shell git config user.email)>"
release:
	semantic-release version --no-push --no-vcs-release --skip-build --no-changelog --no-tag


.PHONY: signed-release
signed-release: release
signed-release: export RELEASE_TAG=$(shell semantic-release version --print-last-released)
signed-release:
	git tag -d "$(RELEASE_TAG)" || true
	git tag -s "$(RELEASE_TAG)" -m "Release $(RELEASE_TAG)"


#------------------------------------------------------------------------------
# Convenience targets to run pre-commit hooks ("lint") and mypy ("typing")
#------------------------------------------------------------------------------

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: typing
typing:
	mypy


#------------------------------------------------------------------------------
# Targets for develpers to debug against a local Postgres run under docker
# compose. Can be used on local machines and in github CI, but not on USDF dev
# nodes since we can't run docker there.
#------------------------------------------------------------------------------

.PHONY: run-compose
run-compose:
	docker compose up --wait

.PHONY: psql
psql: PGPORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
psql: export DB__PASSWORD=INSECURE-PASSWORD
psql: run-compose
	psql postgresql://cm-service:${DB__PASSWORD}@localhost:${PGPORT}/cm-service

.PHONY: test
test: PGPORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
test: export DB__URL=postgresql://cm-service@localhost:${PGPORT}/cm-service
test: export DB__PASSWORD=INSECURE-PASSWORD
test: export DB__TABLE_SCHEMA=cm_service_test
test: export BPS__ARTIFACT_PATH=$(PWD)/output
test: run-compose
	alembic upgrade head
	pytest -vvv --asyncio-mode=auto --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run
run: PGPORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run: export DB__URL=postgresql://cm-service@localhost:${PGPORT}/cm-service
run: export DB__PASSWORD=INSECURE-PASSWORD
run: export DB__ECHO=true
run: export FEATURE_API_V2=1
run: export FEATURE_API_V1=0
run: export FEATURE_DAEMON_V2=0
run: run-compose
	alembic upgrade head
	python3 -m lsst.cmservice.main

.PHONY: run-worker
run-worker: PGPORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run-worker: export DB__URL=postgresql://cm-service@localhost:${PGPORT}/cm-service
run-worker: export DB__PASSWORD=INSECURE-PASSWORD
run-worker: export DB__ECHO=true
run-worker: export FEATURE_API_V2=0
run-worker: export FEATURE_API_V1=0
run-worker: export FEATURE_DAEMON_V2=1
run-worker: export FEATURE_DAEMON_CAMPAIGNS=1
run-worker: export FEATURE_DAEMON_NODES=1
run-worker: export FEATURE_ALLOW_TASK_UPSERT=1
run-worker: run-compose
	alembic upgrade head
	python3 -m lsst.cmservice.daemon

.PHONY: docs
docs:
	uv run script/render_jsonschema.py --clean --html

.PHONY: packages
packages:
	$(MAKE) -C packages/cm-canvas rebuild

.PHONY: run-web
run-web: $(PY_VENV) docs packages
	uv run web

.PHONY: migrate
migrate: export PGUSER=cm-service
migrate: export PGDATABASE=cm-service
migrate: export PGHOST=localhost
migrate: export DB__PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
migrate: export DB__PASSWORD=INSECURE-PASSWORD
migrate: export DB__URL=postgresql://${PGHOST}/${PGDATABASE}
migrate: run-compose
	alembic upgrade head

.PHONY: unmigrate
unmigrate: export PGUSER=cm-service
unmigrate: export PGDATABASE=cm-service
unmigrate: export PGHOST=localhost
unmigrate: export DB__PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
unmigrate: export DB__PASSWORD=INSECURE-PASSWORD
unmigrate: export DB__URL=postgresql://${PGHOST}/${PGDATABASE}
unmigrate: run-compose
	alembic downgrade base


#------------------------------------------------------------------------------
# Targets for running per-developer service instances on USDF Rubin dev nodes,
# using a single shared backend cnpg Postgres in the usdf-cm-dev k8s vcluster.
# Currently used by most devs for development/debug, and also by pilots for
# production runs.
#
# FIXME: TO BE DEPRECATED as soon as we can reliably use shared phalanx service
# for production and sqlite for development/debug.
#------------------------------------------------------------------------------

.PHONY: run-usdf-dev
run-usdf-dev:DB__HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')'
run-usdf-dev: export DB__URL=postgresql://cm-service@${DB__HOST}:5432/cm-service
run-usdf-dev: export DB__PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
run-usdf-dev: export DB__ECHO=true
run-usdf-dev:
	python3 -m lsst.cmservice.main

get-env-%: DB__HOST=$(shell kubectl --cluster=$* -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
get-env-%: export DB__URL=postgresql://cm-servicer@${DB__HOST}:5432/cm-service
get-env-%: export DB__PASSWORD=$(shell kubectl --cluster=$* -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
get-env-%: export DB__ECHO=true
get-env-%:
	rm -f .env.$*
	echo DB__URL=$${DB__URL} > .env.$*
	echo DB__ECHO=$${DB__ECHO} >> .env.$*
	echo DB__PASSWORD=$${DB__PASSWORD} >> .env.$*
