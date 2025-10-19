.PHONY: fmt lint type test security check sbom

fmt:
	ruff format .

lint:
	ruff check .

type:
	mypy .

security:
	bandit -q -r zscripts sample_project

test:
	pytest

check: fmt lint type security test

sbom:
	mkdir -p artifacts/sbom
	cyclonedx-py --format json --output artifacts/sbom/sbom.json
	cyclonedx-py --format xml --output artifacts/sbom/sbom.xml
