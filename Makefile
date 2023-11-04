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
	pip install --upgrade pre-commit
	pre-commit install

.PHONY: update
update: update-deps init

.PHONY: test
test:
	docker compose up --wait --quiet-pull && \
	CM_DATABASE_PORT=$$(docker compose port postgresql 5432 | cut -d: -f2) && \
	CM_ARQ_REDIS_PORT=$$(docker compose port redis 6379 | cut -d: -f2) && \
	export CM_DATABASE_URL=postgresql://cm-service@localhost:$${CM_DATABASE_PORT}/cm-service && \
	export CM_DATABASE_PASSWORD=INSECURE-PASSWORD && \
	export CM_DATABASE_SCHEMA=cm_service_test && \
	export CM_ARQ_REDIS_URL=redis://localhost:$${CM_ARQ_REDIS_PORT}/1 && \
	export CM_ARQ_REDIS_PASSWORD=INSECURE-PASSWORD && \
	pytest -vvv --cov=lsst.cmservice --cov-branch --cov-report=term --cov-report=html

.PHONY: run
run:
	docker compose up --wait && \
	CM_DATABASE_PORT=$$(docker compose port postgresql 5432 | cut -d: -f2) && \
	CM_ARQ_REDIS_PORT=$$(docker compose port redis 6379 | cut -d: -f2) && \
	export CM_DATABASE_URL=postgresql://cm-service@localhost:$${CM_DATABASE_PORT}/cm-service && \
	export CM_DATABASE_PASSWORD=INSECURE-PASSWORD && \
	export CM_DATABASE_ECHO=true && \
	export CM_ARQ_REDIS_URL=redis://localhost:$${CM_ARQ_REDIS_PORT}/1 && \
	export CM_ARQ_REDIS_PASSWORD=INSECURE-PASSWORD && \
	cm-service init && \
	cm-service run

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: typing
typing:
	mypy src tests
