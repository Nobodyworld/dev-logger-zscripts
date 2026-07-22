.PHONY: setup dev fmt format-check lint type security test coverage build deploy quality check release sbom

QUALITY_GATE = python scripts/quality_gate.py

setup:
	python scripts/bootstrap.py || python scripts/bootstrap.py --skip-install

dev:
	$(QUALITY_GATE) quality

fmt:
	ruff format .

format-check:
	$(QUALITY_GATE) format-check

lint:
	$(QUALITY_GATE) lint

type:
	$(QUALITY_GATE) type

security:
	$(QUALITY_GATE) bandit

test:
	$(QUALITY_GATE) tests

coverage:
	$(QUALITY_GATE) coverage

build:
	python scripts/build_artifact.py

deploy: build
	python artifacts/build/zscripts.pyz guardrails > artifacts/build/guardrails.json

quality:
	$(QUALITY_GATE) quality

check:
	$(QUALITY_GATE) check

release:
	$(QUALITY_GATE) release

sbom:
	mkdir -p artifacts/sbom
	cyclonedx-py --format json --output artifacts/sbom/sbom.json
	cyclonedx-py --format xml --output artifacts/sbom/sbom.xml
