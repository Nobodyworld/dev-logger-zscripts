import argparse
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

CATEGORIES: Dict[str, List[str]] = {
    "Data_Processing_and_Analysis": ["pandas", "numpy", "openpyxl"],
    "Machine_Learning_and_Data_Science": ["sklearn", "tensorflow", "torch", "model_work"],
    "Image_Processing_and_Computer_Vision": ["cv2", "PIL", "img2pdf"],
    "File_and_Directory_Management": ["glob", "pathlib", "PyPDF2"],
    "Web_Scraping_and_Internet_Data_Handling": ["requests", "urllib", "bs4", "tiktoken"],
    "Environment_and_Configuration": ["dotenv"],
    "Deep_Learning_Frameworks": ["tensorflow", "torch"],
    "Utility_and_Miscellaneous": ["tqdm"],
    "OpenAI_and_API_Interaction": ["openai"],
}


def categorize_script(file_path: Path, categories: Dict[str, Iterable[str]]) -> List[str]:
    """Return the category labels that match the import statements found in `file_path`."""
    content = file_path.read_text(encoding="utf-8")
    matches = [
        category
        for category, modules in categories.items()
        if any(module in content for module in modules)
    ]
    return matches or ["Uncategorized"]


def organize_scripts(directory: Path, categories: Dict[str, Iterable[str]]) -> None:
    """Create category subdirectories and move scripts that match each category."""
    files_to_move: Dict[str, List[Path]] = defaultdict(list)
    for script_path in directory.rglob("*.py"):
        for category in categorize_script(script_path, categories):
            files_to_move[category].append(script_path)

    for category, scripts in files_to_move.items():
        category_path = directory / category
        category_path.mkdir(exist_ok=True)
        for script_path in scripts:
            destination = category_path / script_path.name
            if destination.exists():
                print(f"Skip (exists): {destination}")
                continue
            shutil.move(str(script_path), destination)
            print(f"Moved: {script_path} -> {destination}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group Python scripts into category subdirectories."
    )
    parser.add_argument(
        "directory", type=Path, help="Root directory containing scripts to organise."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = args.directory.expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    organize_scripts(directory, CATEGORIES)
    print("Script organization complete.")


if __name__ == "__main__":
    main()
