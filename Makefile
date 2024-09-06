default:

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

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: typing
typing:
	mypy src tests

.PHONY: psql
psql: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
psql: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
psql:
	psql postgresql://cm-service:${CM_DATABASE_PASSWORD}@localhost:${CM_DATABASE_PORT}/cm-service

.PHONY: psql-usdf-dev
psql-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
psql-usdf-dev: CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
psql-usdf-dev:
	psql postgresql://cm-service:${CM_DATABASE_PASSWORD}@${CM_DATABASE_HOST}:5432/cm-service

.PHONY: test
test: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
test: export CM_DATABASE_URL=postgresql://cm-service@localhost:${CM_DATABASE_PORT}/cm-service
test: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
test: export CM_DATABASE_SCHEMA=cm_service_test
test: run-compose
	pytest -vvv --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: test-usdf-dev
test-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
test-usdf-dev: export CM_DATABASE_URL=postgresql://cm-service@${CM_DATABASE_HOST}:5432/cm-service
test-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
test-usdf-dev: export CM_DATABASE_SCHEMA=cm_service_test
test-usdf-dev:
	pytest -vvv --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html ${PYTEST_ARGS}

.PHONY: run-compose
run-compose:
	docker compose up --wait

.PHONY: run
run: CM_DATABASE_PORT=$(shell docker compose port postgresql 5432 | cut -d: -f2)
run: export CM_DATABASE_URL=postgresql://cm-service@localhost:${CM_DATABASE_PORT}/cm-service
run: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
run: export CM_DATABASE_ECHO=true
run: run-compose
	cm-service init
	cm-service run

.PHONY: run-usdf-dev
run-usdf-dev: CM_DATABASE_HOST=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get svc/cm-pg-lb -o jsonpath='{..ingress[0].ip}')
run-usdf-dev: export CM_DATABASE_URL=postgresql://cm-service@${CM_DATABASE_HOST}:5432/cm-service
run-usdf-dev: export CM_DATABASE_PASSWORD=$(shell kubectl --cluster=usdf-cm-dev -n cm-service get secret/cm-pg-app -o jsonpath='{.data.password}' | base64 --decode)
run-usdf-dev: export CM_DATABASE_ECHO=true
run-usdf-dev:
	cm-service init
	cm-service run

.PHONY: run-mysql
run-mysql: export CM_DATABASE_URL=sqlite+aiosqlite://///test_cm.db
#run-mysql: export CM_DATABASE_SCHEMA=${USER}
#run-mysql: export CM_DATABASE_PASSWORD=INSECURE-PASSWORD
run-mysql: export CM_DATABASE_ECHO=true
run-mysql:
	cm-service init
	cm-service run
