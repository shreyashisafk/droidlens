"""
Investigation timeline generation for DroidLens.
Formats events into human-readable chronological timeline items with risk indicators.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from ..normalization.schema import Event
from ..detection.risk_engine import RiskAssessment


@dataclass
class TimelineItem:
    """
    Formatted timeline entry for investigator review.
    """
    event_id: str
    timestamp: datetime
    formatted_time: str
    event_type: str
    actor: str
    target: str
    action_narrative: str
    location: str
    risk_score: int
    risk_level: str
    reasons: List[str]

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "formatted_time": self.formatted_time,
            "event_type": self.event_type,
            "actor": self.actor,
            "target": self.target,
            "action_narrative": self.action_narrative,
            "location": self.location,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "reasons": self.reasons,
        }


class TimelineBuilder:
    """
    Builds clean chronological timeline entries from Events and Risk Assessments.
    """

    @classmethod
    def format_narrative(cls, ev: Event) -> str:
        """
        Generate a concise, natural description of what took place in the event.
        """
        meta_parts = []
        if "duration" in ev.metadata and ev.metadata["duration"]:
            meta_parts.append(f"duration {ev.metadata['duration']}s")
        if "amount" in ev.metadata and ev.metadata["amount"]:
            meta_parts.append(f"amount Rs. {float(ev.metadata['amount']):,.2f}")
        if "details" in ev.metadata and ev.metadata["details"]:
            meta_parts.append(f"'{ev.metadata['details']}'")
        if "note" in ev.metadata and ev.metadata["note"]:
            meta_parts.append(f"'{ev.metadata['note']}'")

        meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""

        if ev.event_type == "CALL":
            return f"{ev.actor} called {ev.target}{meta_str}"
        elif ev.event_type == "MESSAGE":
            return f"{ev.actor} sent message to {ev.target}{meta_str}"
        elif ev.event_type == "TRANSACTION":
            return f"{ev.actor} transferred funds to {ev.target}{meta_str}"
        elif ev.event_type == "LOCATION_PING":
            return f"{ev.actor} recorded location ping at {ev.target or ev.location}{meta_str}"
        elif ev.event_type == "SURVEILLANCE":
            return f"Surveillance log recorded for {ev.actor} at {ev.location}{meta_str}"
        else:
            return f"{ev.actor} interacted with {ev.target} via {ev.source}{meta_str}"

    @classmethod
    def build_timeline(
        cls,
        events: List[Event],
        event_risks: Dict[str, RiskAssessment],
        filter_entity: Optional[str] = None,
        min_risk_score: int = 0
    ) -> List[TimelineItem]:
        """
        Construct a chronological sequence of timeline items with optional entity or risk filtering.
        """
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        timeline: List[TimelineItem] = []

        for ev in sorted_events:
            if filter_entity and filter_entity not in [ev.actor, ev.target]:
                continue

            assessment = event_risks.get(ev.event_id, RiskAssessment(ev.event_id, 0, "LOW"))
            if assessment.risk_score < min_risk_score:
                continue

            item = TimelineItem(
                event_id=ev.event_id,
                timestamp=ev.timestamp,
                formatted_time=ev.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                event_type=ev.event_type,
                actor=ev.actor,
                target=ev.target,
                action_narrative=cls.format_narrative(ev),
                location=ev.location or "Unknown",
                risk_score=assessment.risk_score,
                risk_level=assessment.risk_level,
                reasons=assessment.reasons,
            )
            timeline.append(item)

        return timeline
