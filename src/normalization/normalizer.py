"""
Event normalizer for DroidLens.
Maps heterogeneous raw input records into standard Event instances.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
import pandas as pd

from .schema import Event


class EventNormalizer:
    """
    Normalizes diverse dictionary records into standardized Event objects.
    """

    # Field alias lookups
    TIMESTAMP_ALIASES = ["timestamp", "datetime", "date_time", "time", "date", "created_at"]
    EVENT_TYPE_ALIASES = ["event_type", "type", "action", "activity", "category"]
    ACTOR_ALIASES = ["actor", "sender", "from", "caller", "source_entity", "initiator", "origin_user"]
    TARGET_ALIASES = ["target", "receiver", "to", "callee", "destination_entity", "recipient", "target_user"]
    SOURCE_ALIASES = ["source", "origin", "channel", "medium", "data_source", "feed"]
    LOCATION_ALIASES = ["location", "city", "tower", "place", "geo", "area", "address"]
    ID_ALIASES = ["event_id", "record_id", "id", "uid", "txn_id"]

    @classmethod
    def _find_field(cls, record: Dict[str, Any], aliases: List[str]) -> Optional[Any]:
        """Find the first matching key from a list of aliases (case-insensitive)."""
        lower_map = {k.lower(): k for k in record.keys()}
        for alias in aliases:
            if alias.lower() in lower_map:
                val = record[lower_map[alias.lower()]]
                if val is not None and str(val).strip() != "":
                    return val
        return None

    @classmethod
    def _parse_timestamp(cls, val: Any) -> datetime:
        """Robustly parse timestamp into a Python datetime object."""
        if isinstance(val, datetime):
            return val
        if pd.isna(val) or val is None:
            return datetime.now()
        try:
            # Leverage pandas parsing for high flexibility (ISO, formats with / or -)
            dt = pd.to_datetime(val)
            if isinstance(dt, pd.Timestamp):
                return dt.to_pydatetime()
            return datetime.now()
        except Exception:
            return datetime.now()

    @classmethod
    def normalize_record(cls, raw: Dict[str, Any], index: int = 1) -> Event:
        """
        Convert a single raw dictionary record into an Event object.
        """
        event_id = cls._find_field(raw, cls.ID_ALIASES)
        if not event_id:
            event_id = f"EVT-{index:04d}-{str(uuid.uuid4())[:6]}"
        else:
            event_id = str(event_id).strip()

        raw_ts = cls._find_field(raw, cls.TIMESTAMP_ALIASES)
        timestamp = cls._parse_timestamp(raw_ts)

        event_type = cls._find_field(raw, cls.EVENT_TYPE_ALIASES)
        event_type = str(event_type).strip().upper() if event_type else "OTHER"

        actor = cls._find_field(raw, cls.ACTOR_ALIASES)
        actor = str(actor).strip() if actor else "UNKNOWN"

        target = cls._find_field(raw, cls.TARGET_ALIASES)
        target = str(target).strip() if target else "UNKNOWN"

        source = cls._find_field(raw, cls.SOURCE_ALIASES)
        source = str(source).strip() if source else "generic"

        location = cls._find_field(raw, cls.LOCATION_ALIASES)
        location = str(location).strip() if location else None

        # Build metadata from non-core fields
        consumed_keys = set()
        for group in [
            cls.ID_ALIASES, cls.TIMESTAMP_ALIASES, cls.EVENT_TYPE_ALIASES,
            cls.ACTOR_ALIASES, cls.TARGET_ALIASES, cls.SOURCE_ALIASES, cls.LOCATION_ALIASES
        ]:
            consumed_keys.update(k.lower() for k in group)

        metadata: Dict[str, Any] = {}
        # If there's an existing nested metadata dictionary, merge it
        if "meta" in raw and isinstance(raw["meta"], dict):
            metadata.update(raw["meta"])
        if "metadata" in raw and isinstance(raw["metadata"], dict):
            metadata.update(raw["metadata"])

        for k, v in raw.items():
            if k.lower() not in consumed_keys and k.lower() not in ["meta", "metadata"] and v is not None and not pd.isna(v):
                metadata[k] = v

        return Event(
            event_id=event_id,
            timestamp=timestamp,
            event_type=event_type,
            source=source,
            actor=actor,
            target=target,
            location=location,
            metadata=metadata
        )

    @classmethod
    def normalize(cls, records: List[Dict[str, Any]]) -> List[Event]:
        """
        Normalize a list of raw records and sort chronologically by timestamp.
        """
        events = [cls.normalize_record(rec, idx + 1) for idx, rec in enumerate(records)]
        # Sort chronologically
        events.sort(key=lambda e: e.timestamp)
        return events
