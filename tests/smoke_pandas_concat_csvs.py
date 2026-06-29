from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd

from zscripts.helpers.pandas.concat_csvs import consolidate_files


def run() -> None:
    fixtures = Path("tests/fixtures/pandas/concat_csvs")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name in ("a.csv", "b.csv"):
            shutil.copy(fixtures / name, tmp_path / name)

        consolidate_files(str(tmp_path))

        out = tmp_path / "consolidated.csv"
        assert out.exists(), "consolidated.csv not created"
        df = pd.read_csv(out)
        assert len(df) == 3
        assert set(df.columns) == {"id", "value"}


if __name__ == "__main__":
    run()
    print("pandas concat_csvs smoke test passed")
