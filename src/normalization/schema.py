"""
Event schema and data structures for DroidLens.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Event:
    """
    Standardized internal representation of an investigative event.
    """
    event_id: str
    timestamp: datetime
    event_type: str
    source: str
    actor: str
    target: str
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the Event to a standard dictionary format."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "source": self.source,
            "actor": self.actor,
            "target": self.target,
            "location": self.location or "Unknown",
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create an Event from a dictionary with robust parsing."""
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif not isinstance(ts, datetime):
            ts = datetime.now()

        return cls(
            event_id=str(data.get("event_id", "")),
            timestamp=ts,
            event_type=str(data.get("event_type", "OTHER")).upper(),
            source=str(data.get("source", "generic")),
            actor=str(data.get("actor", "UNKNOWN")),
            target=str(data.get("target", "UNKNOWN")),
            location=data.get("location") if data.get("location") else None,
            metadata=data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {},
        )
