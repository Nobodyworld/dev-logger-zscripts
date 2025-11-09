import os
from pathlib import Path
from typing import Iterable

from helpers.utilities.paths import org_path


def rename_with_av_prefix(folder: Path) -> Iterable[tuple[str, str]]:
    """Rename images by replacing prefix with 'AV_' and normalizing separators.

    Yields tuples of (old_name, new_name).
    """
    for file in os.listdir(folder):
        if file.lower().endswith((".jpeg", ".jpg")):
            new_file = file.replace("-", "_")
            parts = new_file.rsplit("_", 1)
            new_file_name = ("AV_" + parts[1]) if len(parts) == 2 else ("AV_" + new_file)

            # Ensure uniqueness
            candidate = folder / new_file_name
            if candidate.exists():
                extension = new_file_name.rsplit(".", 1)[1]
                count = 1
                while (folder / f"AV_{count}.{extension}").exists():
                    count += 1
                new_file_name = f"AV_{count}.{extension}"

            os.rename(folder / file, folder / new_file_name)
            yield file, new_file_name


if __name__ == "__main__":
    target = org_path("Revenue Streams", "images_process", "b.edit_these")
    for old, new in rename_with_av_prefix(target):
        print(f"Renamed {old} to {new}")
