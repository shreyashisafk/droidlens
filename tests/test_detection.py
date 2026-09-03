"""
Unit tests for the explainable detection rules and risk engine.
"""

from pathlib import Path
from src.ingestion.csv_loader import load_csv
from src.normalization.normalizer import EventNormalizer
from src.entities.extractor import EntityExtractor
from src.detection.risk_engine import RiskEngine


def test_risk_engine_evaluation():
    csv_path = Path(__file__).parent.parent / "data" / "raw" / "synthetic_investigation.csv"
    events = EventNormalizer.normalize(load_csv(csv_path))
    profiles = EntityExtractor.extract_profiles(events)

    engine = RiskEngine()
    event_assessments = engine.assess_events(events, profiles)
    entity_assessments = engine.assess_entities(events, event_assessments, profiles)

    assert len(event_assessments) == len(events)
    assert len(entity_assessments) == len(profiles)

    # Verify communication burst flag on 14:00+ cluster
    burst_event = next(e for e in events if e.event_id == "EVT-004")
    assessment_burst = event_assessments[burst_event.event_id]
    assert assessment_burst.risk_score > 0
    assert any("burst" in r.lower() for r in assessment_burst.reasons)

    # Verify high value transaction flag on EVT-010 (Rs. 250,000)
    txn_event = next(e for e in events if e.event_id == "EVT-010")
    assessment_txn = event_assessments[txn_event.event_id]
    assert assessment_txn.risk_score >= 25
    assert any("250,000" in r for r in assessment_txn.reasons)

    # Verify unusual movement flag on EVT-018 (Delhi to Mumbai in 15 mins)
    move_event = next(e for e in events if e.event_id == "EVT-018")
    assessment_move = event_assessments[move_event.event_id]
    assert assessment_move.risk_score > 0
    assert any("movement" in r.lower() or "transit" in r.lower() for r in assessment_move.reasons)

    # Check key entity risk scores (Person_A, Person_B)
    assert entity_assessments["Person_B"].risk_score >= 50
    assert entity_assessments["Person_B"].flagged_events_count > 0
    assert len(entity_assessments["Person_B"].key_findings) > 0
