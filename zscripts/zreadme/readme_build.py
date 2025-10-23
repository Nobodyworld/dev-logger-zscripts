"""Compile README.md from curated text fragments stored alongside the source."""

from __future__ import annotations

from pathlib import Path

# TODO - Allow configuring README sections via CLI arguments or config file.


def compile_readme() -> None:
    """Write the combined README.md file using the canonical section ordering."""

    readme_dir = Path("zscripts/zreadme")
    build_order = [
        "0-Overview.txt",
        "1-Configuration.txt",
        "2-CLI.txt",
        "3-Sample-Project.txt",
        "4-Migration.txt",
    ]

    compiled_content: list[str] = []
    # TODO - Add checksum validation to detect stale section files.
    for filename in build_order:
        path = readme_dir / filename.strip()
        try:
            compiled_content.append(path.read_text(encoding="utf-8").rstrip())
        except FileNotFoundError:
            print(f"Warning: {path} not found and will be skipped.")
            # TODO - Hook into logging module instead of printing directly.
        except UnicodeDecodeError as error:
            print(f"Error reading {path}: {error}")
            # TODO - Capture read failures for reporting in CI pipelines.

    output_readme_path = Path("README.md")
    output_readme_path.write_text("\n\n".join(compiled_content) + "\n", encoding="utf-8")
    # TODO - Preserve existing README header comments when recompiling output.
    print(f"Readme compiled and saved to {output_readme_path.resolve()}")


if __name__ == "__main__":
    compile_readme()
