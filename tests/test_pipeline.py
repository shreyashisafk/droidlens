"""
End-to-end pipeline verification test for DroidLens.
"""

from pathlib import Path
from src.pipeline import DroidLensPipeline


def test_pipeline_end_to_end():
    sample_csv = Path(__file__).parent.parent / "data" / "raw" / "synthetic_investigation.csv"
    pipeline = DroidLensPipeline(correlation_window_minutes=30)
    result = pipeline.run_from_file(sample_csv)

    assert result.summary_metrics["total_events"] == 23
    assert result.summary_metrics["total_entities"] >= 6
    assert result.summary_metrics["flagged_events_count"] > 0
    assert result.summary_metrics["incident_clusters_count"] > 0
    assert len(result.key_entities) > 0
    assert len(result.timeline) == 23
    assert len(result.plot_data.node_ids) == result.summary_metrics["total_entities"]
