import glob
import logging
import os

import pandas as pd
from helpers.utilities.paths import org_path

logger = logging.getLogger(__name__)


def consolidate_files(directory: str) -> None:
    """Concatenate all CSVs in a directory into consolidated.csv.

    Args:
        directory: Path to directory containing CSV files to consolidate.

    Raises:
        FileNotFoundError: If directory does not exist.
        ValueError: If no CSV files found in directory.
        RuntimeError: If concatenation or file writing fails.
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory does not exist: {directory}")

    # Get all csv files from the directory
    csv_files = glob.glob(os.path.join(directory, "*.csv"))

    if not csv_files:
        raise ValueError(f"No CSV files found in directory {directory}")

    df_list = []
    for filename in csv_files:
        try:
            # Read each csv file and append it to the df_list
            df = pd.read_csv(filename, index_col=None, header=0)
            df_list.append(df)
            logger.info("File %s read successfully", filename)
        except Exception as e:
            logger.error("Error reading file %s: %s", filename, str(e))
            raise RuntimeError(f"Failed to read CSV file {filename}") from e

    # Concatenate all dataframes in the df_list
    try:
        frame = pd.concat(df_list, axis=0, ignore_index=True)
    except Exception as e:
        logger.error("Error concatenating dataframes: %s", str(e))
        raise RuntimeError("Failed to concatenate dataframes") from e

    # Write the concatenated dataframe to a new csv file
    output_path = os.path.join(directory, "consolidated.csv")
    try:
        frame.to_csv(output_path, index=False)
        logger.info("Consolidated file written to %s", output_path)
    except Exception as e:
        logger.error("Error writing consolidated file: %s", str(e))
        raise RuntimeError(f"Failed to write consolidated file to {output_path}") from e


def main() -> None:
    """Run consolidation for predefined directories."""
    try:
        consolidate_files(str(org_path("data", "p_query_mst", "product", "commod", "us")))
        consolidate_files(str(org_path("data", "p_query_mst", "product", "commod", "world")))
    except Exception as e:
        logger.error("Consolidation failed: %s", e)
        raise


if __name__ == "__main__":
    main()
