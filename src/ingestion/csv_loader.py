"""
CSV data loader for DroidLens.
Loads tabular records and provides flexible column mapping.
"""

from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Union
import pandas as pd


def load_csv(file_input: Union[str, Path, StringIO, bytes]) -> List[Dict[str, Any]]:
    """
    Load records from a CSV file path, string buffer, or bytes.
    Returns a list of raw dictionaries.
    """
    if isinstance(file_input, bytes):
        df = pd.read_csv(StringIO(file_input.decode("utf-8", errors="replace")))
    elif isinstance(file_input, (str, Path)):
        df = pd.read_csv(file_input)
    elif hasattr(file_input, "read"):
        df = pd.read_csv(file_input)
    else:
        raise ValueError(f"Unsupported input type for CSV loader: {type(file_input)}")

    # Standardize column headers: lowercase and strip whitespace
    df.columns = [str(col).strip().lower() for col in df.columns]
    
    # Replace NaN values with None
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    return records
