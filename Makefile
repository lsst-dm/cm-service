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

.PHONE: test
test: export CM_DATABASE_URL = postgresql://cm-service@127.0.0.1/cm-service
test: export CM_DATABASE_PASSWORD = INSECURE-PASSWORD
test: export CM_DATABASE_SCHEMA = cm_service_test
test: export CM_REDIS_HOST = 127.0.0.1
test:
	docker compose up --wait --quiet-pull
	pytest -vv --cov

.PHONY: run
run: export CM_DATABASE_URL = postgresql://cm-service@127.0.0.1/cm-service
run: export CM_DATABASE_PASSWORD = INSECURE-PASSWORD
run: export CM_DATABASE_ECHO = true
run: export CM_REDIS_HOST = 127.0.0.1
run:
	docker compose up --wait
	cm-service init
	cm-service run

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: typing
typing:
	mypy src tests
