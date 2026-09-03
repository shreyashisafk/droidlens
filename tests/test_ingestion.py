"""
Unit tests for data ingestion, normalization, and entity extraction.
"""

from pathlib import Path
from src.ingestion.csv_loader import load_csv
from src.ingestion.json_loader import load_json
from src.normalization.normalizer import EventNormalizer
from src.entities.extractor import EntityExtractor


def test_csv_ingestion_and_normalization():
    csv_path = Path(__file__).parent.parent / "data" / "raw" / "synthetic_investigation.csv"
    assert csv_path.exists(), "Sample CSV dataset must exist"

    raw_records = load_csv(csv_path)
    assert len(raw_records) == 23

    events = EventNormalizer.normalize(raw_records)
    assert len(events) == 23

    # Ensure sorting by timestamp
    for i in range(len(events) - 1):
        assert events[i].timestamp <= events[i+1].timestamp

    # Check first event
    assert events[0].event_id == "EVT-001"
    assert events[0].actor == "Person_A"
    assert events[0].target == "Person_B"
    assert events[0].event_type == "CALL"


def test_json_ingestion_and_normalization():
    json_path = Path(__file__).parent.parent / "data" / "raw" / "synthetic_investigation.json"
    assert json_path.exists(), "Sample JSON dataset must exist"

    raw_records = load_json(json_path)
    assert len(raw_records) == 23

    events = EventNormalizer.normalize(raw_records)
    assert len(events) == 23
    assert events[0].actor == "Person_A"
    assert events[0].target == "Person_B"


def test_entity_extraction():
    csv_path = Path(__file__).parent.parent / "data" / "raw" / "synthetic_investigation.csv"
    events = EventNormalizer.normalize(load_csv(csv_path))
    profiles = EntityExtractor.extract_profiles(events)

    assert "Person_A" in profiles
    assert "Person_B" in profiles
    assert profiles["Person_A"].category == "PERSON"
    assert profiles["Person_B"].total_events >= 10
    assert len(profiles["Person_B"].connected_entities) >= 4
