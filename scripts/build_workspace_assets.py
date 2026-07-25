"""Copy the deterministic Vite build into package data for wheel creation."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "workspace-ui" / "dist"
TARGET = ROOT / "zscripts" / "workspace_static"
THIRD_PARTY_NOTICES = ROOT / "workspace-ui" / "THIRD_PARTY_NOTICES.md"


def build_workspace_assets() -> None:
    """Replace generated package data with the current complete Vite output."""

    index = SOURCE / "index.html"
    if not index.is_file():
        raise RuntimeError(
            "Workspace build is missing. Run 'pnpm --dir workspace-ui build' before packaging."
        )
    if TARGET.exists():
        resolved_target = TARGET.resolve()
        expected_parent = (ROOT / "zscripts").resolve()
        if resolved_target.parent != expected_parent or resolved_target.name != "workspace_static":
            raise RuntimeError("Refusing to replace an unexpected workspace asset directory.")
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET, copy_function=shutil.copyfile)
    shutil.copyfile(THIRD_PARTY_NOTICES, TARGET / THIRD_PARTY_NOTICES.name)
    if not (TARGET / "index.html").is_file():
        raise RuntimeError("Workspace package-data copy did not produce index.html.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    build_workspace_assets()
    print(f"Packaged workspace assets: {TARGET.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
