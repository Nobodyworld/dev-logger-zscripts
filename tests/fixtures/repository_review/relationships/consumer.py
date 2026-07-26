"""An import made ambiguous by duplicate supported module names."""

import pkg.shared  # noqa: F401 - fixture-only ambiguous import evidence
