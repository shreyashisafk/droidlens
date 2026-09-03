"""
Temporal correlation engine for DroidLens.
Clusters chronologically adjacent events sharing entities into correlated incident chains.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Set
from ..normalization.schema import Event
from ..detection.risk_engine import RiskAssessment


@dataclass
class CorrelationCluster:
    """
    A correlated group of temporally and relationally linked events.
    """
    cluster_id: str
    start_time: datetime
    end_time: datetime
    events: List[Event] = field(default_factory=list)
    entities_involved: Set[str] = field(default_factory=set)
    primary_locations: Set[str] = field(default_factory=set)
    peak_risk_score: int = 0
    summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "cluster_id": self.cluster_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": int((self.end_time - self.start_time).total_seconds() / 60),
            "event_count": len(self.events),
            "entities_involved": sorted(list(self.entities_involved)),
            "primary_locations": sorted(list(self.primary_locations)),
            "peak_risk_score": self.peak_risk_score,
            "summary": self.summary,
        }


class TemporalCorrelator:
    """
    Correlates events into meaningful clusters based on a configurable sliding time window.
    """

    def __init__(self, default_window_minutes: int = 30):
        self.default_window = timedelta(minutes=default_window_minutes)

    def correlate(
        self,
        events: List[Event],
        event_risks: Dict[str, RiskAssessment],
        window_minutes: int = 30
    ) -> List[CorrelationCluster]:
        """
        Group events into incident clusters where consecutive events occur within the window
        and share at least one participant entity.
        """
        if not events:
            return []

        window = timedelta(minutes=window_minutes)
        # Ensure events are sorted chronologically
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        clusters: List[CorrelationCluster] = []
        current_cluster_events: List[Event] = [sorted_events[0]]
        current_entities: Set[str] = {sorted_events[0].actor, sorted_events[0].target} - {"UNKNOWN", None}

        for ev in sorted_events[1:]:
            ev_entities = {ev.actor, ev.target} - {"UNKNOWN", None}
            prev_event = current_cluster_events[-1]
            time_diff = ev.timestamp - prev_event.timestamp

            # Check if this event continues the current cluster
            shares_entity = bool(current_entities.intersection(ev_entities))
            within_window = time_diff <= window

            if within_window and (shares_entity or len(current_cluster_events) == 1):
                current_cluster_events.append(ev)
                current_entities.update(ev_entities)
            else:
                # Seal current cluster and begin new one
                clusters.append(self._build_cluster(len(clusters) + 1, current_cluster_events, event_risks))
                current_cluster_events = [ev]
                current_entities = ev_entities

        if current_cluster_events:
            clusters.append(self._build_cluster(len(clusters) + 1, current_cluster_events, event_risks))

        return clusters

    @staticmethod
    def _build_cluster(
        index: int,
        cluster_events: List[Event],
        event_risks: Dict[str, RiskAssessment]
    ) -> CorrelationCluster:
        """
        Build and summarize a single CorrelationCluster.
        """
        start_t = cluster_events[0].timestamp
        end_t = cluster_events[-1].timestamp

        entities: Set[str] = set()
        locations: Set[str] = set()
        peak_risk = 0

        for ev in cluster_events:
            if ev.actor and ev.actor != "UNKNOWN":
                entities.add(ev.actor)
            if ev.target and ev.target != "UNKNOWN":
                entities.add(ev.target)
            if ev.location and ev.location != "Unknown":
                locations.add(ev.location)
            risk = event_risks.get(ev.event_id).risk_score if (event_risks and ev.event_id in event_risks) else 0
            if risk > peak_risk:
                peak_risk = risk

        duration_min = int((end_t - start_t).total_seconds() / 60)
        types_summary = ", ".join(sorted(list({e.event_type for e in cluster_events})))

        summary = (
            f"Cluster of {len(cluster_events)} event(s) [{types_summary}] over {duration_min} min "
            f"involving {len(entities)} entities."
        )

        return CorrelationCluster(
            cluster_id=f"INC-{index:03d}",
            start_time=start_t,
            end_time=end_t,
            events=cluster_events,
            entities_involved=entities,
            primary_locations=locations,
            peak_risk_score=peak_risk,
            summary=summary,
        )
