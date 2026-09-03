"""
Ingestion modules for loading structured data from various file formats.
"""

from .csv_loader import load_csv
from .json_loader import load_json

__all__ = ["load_csv", "load_json"]
