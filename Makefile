.PHONY: setup dev fmt format-check lint type security test coverage build deploy quality check sbom

setup:
	python scripts/bootstrap.py || python scripts/bootstrap.py --skip-install

dev:
	python scripts/dev_start.py

MYPY_TARGETS = \
	zscripts/application \
	zscripts/config.py \
	zscripts/configuration.py \
	zscripts/observability/logging.py \
	zscripts/observability/metrics.py \
	zscripts/observability/health.py \
	zscripts/observability/instrumentation.py \
	zscripts/extensions/scaffolding.py \
	zscripts/schemas

fmt:
	ruff format .

format-check:
	ruff format --check .

lint:
	ruff check .

type:
	mypy $(MYPY_TARGETS)

security:
	bandit -q -r zscripts examples/sample_project

test:
	pytest

coverage:
	python -m coverage run -m pytest
	mkdir -p artifacts/coverage
	python -m coverage json -o artifacts/coverage/coverage.json
	python -m coverage report

build:
	python scripts/build_artifact.py

deploy: build
	python artifacts/build/zscripts.pyz guardrails > artifacts/build/guardrails.json

quality:
	python scripts/dev_start.py

check: format-check lint type security test

sbom:
	mkdir -p artifacts/sbom
	cyclonedx-py --format json --output artifacts/sbom/sbom.json
	cyclonedx-py --format xml --output artifacts/sbom/sbom.xml
