"""
Unit tests for network graph builder, temporal correlator, and timeline generation.
"""

from pathlib import Path
from src.ingestion.csv_loader import load_csv
from src.normalization.normalizer import EventNormalizer
from src.entities.extractor import EntityExtractor
from src.detection.risk_engine import RiskEngine
from src.correlation.graph import NetworkGraphBuilder
from src.correlation.correlator import TemporalCorrelator
from src.correlation.timeline import TimelineBuilder


def test_graph_and_correlation_pipeline():
    csv_path = Path(__file__).parent.parent / "data" / "raw" / "synthetic_investigation.csv"
    events = EventNormalizer.normalize(load_csv(csv_path))
    profiles = EntityExtractor.extract_profiles(events)

    engine = RiskEngine()
    event_risks = engine.assess_events(events, profiles)
    entity_risks = engine.assess_entities(events, event_risks, profiles)

    # 1. Build Graph
    G = NetworkGraphBuilder.build_graph(events, profiles, event_risks, entity_risks)
    assert len(G.nodes) >= 6
    assert len(G.edges) >= 6

    # 2. Check Key Entities
    key_entities = NetworkGraphBuilder.get_key_entities(G, top_n=3)
    assert len(key_entities) == 3
    key_ids = [k["entity_id"] for k in key_entities]
    assert "Person_B" in key_ids or "Person_A" in key_ids

    # 3. Generate Plotly Data
    plot_data = NetworkGraphBuilder.generate_plot_data(G)
    assert len(plot_data.node_x) == len(G.nodes)
    assert len(plot_data.edge_x) > 0

    # 4. Correlator
    correlator = TemporalCorrelator(default_window_minutes=30)
    clusters = correlator.correlate(events, event_risks, window_minutes=30)
    assert len(clusters) > 0
    # The 14:00 - 14:40 cluster should have multiple events and high peak risk
    incident_clusters = [c for c in clusters if c.peak_risk_score >= 30]
    assert len(incident_clusters) >= 1

    # 5. Timeline
    timeline = TimelineBuilder.build_timeline(events, event_risks)
    assert len(timeline) == len(events)
    assert timeline[0].formatted_time == "2026-08-29 09:15:00"
