from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_removed_duplicate_ml_modules_remain_absent() -> None:
    removed_modules = [
        ROOT / "zscripts/helpers/machine_learning/model_2.py",
        ROOT / "zscripts/helpers/machine_learning/model_copy_4.py",
        ROOT / "zscripts/helpers/machine_learning/torccaahh.py",
    ]

    unexpected = [
        str(path.relative_to(ROOT)) for path in removed_modules if path.exists()
    ]
    assert not unexpected, f"Unexpected duplicate modules present: {unexpected}"
