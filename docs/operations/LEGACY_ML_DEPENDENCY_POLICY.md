# Legacy ML Managed-Dependency Policy

Status: owner-approved security boundary under issue #130. Phase 2B remains
unauthorized.

Effective base SHA:

`2275cf10b68e7cd9ed1cb8ac35377789e94fe2c4`

The machine-readable decision record is
[`legacy_ml_dependency_policy.json`](legacy_ml_dependency_policy.json).

## Decision

Zscripts does not provision Torch or TorchText through repository-managed
requirements or project extras.

The `helpers-ml` extra remains available for the reviewed lightweight managed
dependencies:

- `scikit-learn>=1.7.2`
- `tiktoken>=0.12.0`

`configs/requirements/ml.txt` provides the exact reviewed profile for those two
dependencies and intentionally contains no Torch line.

## Legacy source status

All 154 tracked helper modules remain included in the wheel during Phase 2A.
The six modules under `zscripts/helpers/machine_learning` remain present and
unchanged. Five of those modules import Torch; several also reference TorchText,
obsolete import paths, or import-time organization-coupled behavior.

Those files are retained as legacy compatibility material. They are not part of
the supported core, are not exposed through `configs/registry.yaml`, are not
re-exported by `zscripts.helpers.machine_learning`, and are not validated as a
supported ML runtime by the default test suite.

Users who deliberately run that historical source must provision and own a
separate environment. Zscripts does not recommend a Torch/TorchText combination,
claim compatibility, or provide support for that environment.

## Rationale

A Torch-only upgrade would remove dependency alerts without creating a coherent
supported ML surface. The repository evidence shows no maintained product
consumer, no registry contract, no package re-export, one non-collected manual
smoke file, undeclared TorchText use, and legacy import/runtime risks.

Removing the managed dependency is therefore narrower and more accurate than:

1. upgrading Torch while implying unsupported compatibility; or
2. continuing to install an affected frozen version under a time-bounded risk
   acceptance.

Security alert details remain in GitHub Security. Public records contain only
the sanitized owner decision and dependency boundary.

## Preserved contracts

This decision does not:

- remove, move, rename, repair, modernize, or execute helper source;
- remove any of the 154 helper modules from the wheel;
- change package discovery;
- change any of the seven temporary compatibility points;
- change any of the 13 registry keys or their targets;
- add a compatibility shim;
- complete the deprecation cycle;
- authorize Phase 2B; or
- create a release, tag, package publication, or stable-support claim.

## Validation contract

The repository must prove that:

- no project-managed requirement or extra resolves Torch;
- `helpers-ml` retains only its declared non-Torch dependencies;
- all 154 helper modules remain wheel-included;
- helper-source and registry digests remain unchanged;
- package discovery remains unchanged;
- the five historical Torch-importing modules remain present;
- ordinary quality, packaging, release, redaction, and secret-scanning gates
  continue to pass; and
- the final PR remains unmerged until separately authorized by exact head SHA.
