"""Invoke pytest so coverage can be gathered via ``python -m trace``."""

from __future__ import annotations

import sys

import pytest


def main() -> int:
    """Execute pytest with the provided command-line arguments."""

    return pytest.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
