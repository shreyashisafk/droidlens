"""
Unified end-to-end investigation pipeline for DroidLens.
Coordinates loading, normalization, risk assessment, network analysis, and timeline building.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

# Ensure root DroidLens directory is on sys.path for direct script execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import networkx as nx

from src.ingestion.csv_loader import load_csv
from src.ingestion.json_loader import load_json
from src.normalization.normalizer import EventNormalizer
from src.normalization.schema import Event
from src.entities.extractor import EntityExtractor, EntityProfile
from src.detection.risk_engine import RiskEngine, RiskAssessment, EntityRiskAssessment
from src.correlation.graph import NetworkGraphBuilder, GraphData
from src.correlation.correlator import TemporalCorrelator, CorrelationCluster
from src.correlation.timeline import TimelineBuilder, TimelineItem


@dataclass
class PipelineResult:
    """
    Complete analysis result produced by the DroidLens pipeline.
    """
    events: List[Event]
    profiles: Dict[str, EntityProfile]
    event_risks: Dict[str, RiskAssessment]
    entity_risks: Dict[str, EntityRiskAssessment]
    graph: nx.Graph
    key_entities: List[Dict]
    clusters: List[CorrelationCluster]
    timeline: List[TimelineItem]
    plot_data: GraphData
    summary_metrics: Dict[str, Any]


class DroidLensPipeline:
    """
    Master pipeline runner.
    """

    def __init__(self, risk_engine: Optional[RiskEngine] = None, correlation_window_minutes: int = 30):
        self.risk_engine = risk_engine or RiskEngine()
        self.correlator = TemporalCorrelator(default_window_minutes=correlation_window_minutes)
        self.correlation_window = correlation_window_minutes

    def run_from_file(
        self,
        file_input: Union[str, Path, bytes, Any],
        file_format: str = "csv",
        correlation_window_minutes: Optional[int] = None
    ) -> PipelineResult:
        """
        Execute full pipeline from an input file (path, bytes, or file-like object).
        """
        fmt = file_format.lower()
        if fmt == "csv" or (isinstance(file_input, (str, Path)) and str(file_input).endswith(".csv")):
            raw_records = load_csv(file_input)
        elif fmt == "json" or (isinstance(file_input, (str, Path)) and str(file_input).endswith(".json")):
            raw_records = load_json(file_input)
        else:
            # Attempt CSV first, fallback to JSON
            try:
                raw_records = load_csv(file_input)
            except Exception:
                raw_records = load_json(file_input)

        return self.run_from_records(raw_records, correlation_window_minutes)

    def run_from_records(
        self,
        raw_records: List[Dict[str, Any]],
        correlation_window_minutes: Optional[int] = None
    ) -> PipelineResult:
        """
        Execute pipeline given a list of raw dictionary records.
        """
        window = correlation_window_minutes or self.correlation_window

        # 1. Normalize
        events = EventNormalizer.normalize(raw_records)

        # 2. Extract Entities & Profiles
        profiles = EntityExtractor.extract_profiles(events)

        # 3. Assess Risks
        event_risks = self.risk_engine.assess_events(events, profiles)
        entity_risks = self.risk_engine.assess_entities(events, event_risks, profiles)

        # 4. Build Graph & Compute Centrality
        graph = NetworkGraphBuilder.build_graph(events, profiles, event_risks, entity_risks)
        key_entities = NetworkGraphBuilder.get_key_entities(graph, top_n=10)
        plot_data = NetworkGraphBuilder.generate_plot_data(graph)

        # 5. Temporal Clustering
        clusters = self.correlator.correlate(events, event_risks, window_minutes=window)

        # 6. Timeline Generation
        timeline = TimelineBuilder.build_timeline(events, event_risks)

        # 7. Summary Metrics
        flagged_events = [e for e in events if event_risks.get(e.event_id, RiskAssessment(e.event_id, 0, "LOW")).risk_score >= 30]
        critical_events = [e for e in events if event_risks.get(e.event_id, RiskAssessment(e.event_id, 0, "LOW")).risk_level in ["HIGH", "CRITICAL"]]
        high_risk_entities = [ent for ent, r in entity_risks.items() if r.risk_score >= 50]

        summary_metrics = {
            "total_events": len(events),
            "total_entities": len(profiles),
            "flagged_events_count": len(flagged_events),
            "critical_events_count": len(critical_events),
            "high_risk_entities_count": len(high_risk_entities),
            "incident_clusters_count": len(clusters),
            "total_relationships": graph.number_of_edges(),
        }

        return PipelineResult(
            events=events,
            profiles=profiles,
            event_risks=event_risks,
            entity_risks=entity_risks,
            graph=graph,
            key_entities=key_entities,
            clusters=clusters,
            timeline=timeline,
            plot_data=plot_data,
            summary_metrics=summary_metrics,
        )


if __name__ == "__main__":
    # Self-test CLI runner
    sample_csv = project_root / "data" / "raw" / "synthetic_investigation.csv"
    pipeline = DroidLensPipeline()
    result = pipeline.run_from_file(sample_csv)
    print("=" * 60)
    print(" DROIDLENS PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    for k, v in result.summary_metrics.items():
        print(f" {k.replace('_', ' ').title():<28}: {v}")
    print("-" * 60)
    print(" TOP KEY / HIGH-RISK ENTITIES:")
    for ent in result.key_entities[:3]:
        print(f" • {ent['entity_id']} [{ent['category']}] — Risk: {ent['risk_score']}/100 ({ent['risk_level']}), Degree: {ent['degree']}")
    print("=" * 60)
