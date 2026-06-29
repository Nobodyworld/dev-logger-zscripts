from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from zscripts.helpers.pandas.excel_to_json_posts import process_excel_file


def run() -> None:
    fixtures = Path("tests/fixtures/pandas/posts.json")
    posts = json.loads(fixtures.read_text(encoding="utf-8"))
    df = pd.DataFrame(posts)

    with tempfile.TemporaryDirectory() as tmp:
        xlsx = Path(tmp) / "posts.xlsx"
        with pd.ExcelWriter(xlsx) as writer:
            df.to_excel(writer, sheet_name="Sheet1", index=False)

        out = process_excel_file(str(xlsx), "Sheet1")
        assert isinstance(out, list) and len(out) == 2
        cats = set(out[0]["categories"])  # type: ignore[index]
        tags = set(out[0]["tags"])  # type: ignore[index]
        assert "news" in cats and "tech" in cats
        assert "ai" in tags and "ml" in tags


if __name__ == "__main__":
    run()
    print("pandas excel_to_json_posts smoke test passed")
