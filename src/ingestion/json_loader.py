"""
JSON data loader for DroidLens.
Loads structured records from JSON files, raw strings, or byte streams.
"""

from io import StringIO
import json
from pathlib import Path
from typing import Any, Dict, List, Union


def load_json(file_input: Union[str, Path, StringIO, bytes]) -> List[Dict[str, Any]]:
    """
    Load records from a JSON file path, string, or bytes.
    Supports either a list of JSON objects or a JSON object containing an 'events' / 'records' key.
    """
    if isinstance(file_input, bytes):
        raw_text = file_input.decode("utf-8", errors="replace")
        data = json.loads(raw_text)
    elif isinstance(file_input, (str, Path)):
        path = Path(file_input)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            # Treat as raw JSON string
            data = json.loads(str(file_input))
    elif hasattr(file_input, "read"):
        content = file_input.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        data = json.loads(content)
    else:
        raise ValueError(f"Unsupported input type for JSON loader: {type(file_input)}")

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        for key in ["events", "records", "data", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    else:
        raise ValueError("Invalid JSON format: Expected a list of records or a dictionary containing records.")
