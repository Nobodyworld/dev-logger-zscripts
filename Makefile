.PHONY: fmt lint type test security check sbom

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

lint:
	ruff check .

type:
	mypy $(MYPY_TARGETS)

security:
	bandit -q -r zscripts sample_project

test:
	pytest

coverage:
	coverage run -m pytest
	coverage json -o reports/coverage.json
	coverage report

quality:
	python scripts/dev_start.py

check: fmt lint type security test

sbom:
	mkdir -p artifacts/sbom
	cyclonedx-py --format json --output artifacts/sbom/sbom.json
	cyclonedx-py --format xml --output artifacts/sbom/sbom.xml
