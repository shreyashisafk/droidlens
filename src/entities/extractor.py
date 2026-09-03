"""
Entity extraction and profile aggregation for DroidLens.
Identifies unique actors/targets/locations and categorizes entity types.
"""

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Dict, List, Optional, Set
from ..normalization.schema import Event


@dataclass
class EntityProfile:
    """
    Profile aggregating statistics and interactions for a unique entity.
    """
    entity_id: str
    category: str  # PERSON, PHONE, ACCOUNT, LOCATION, VEHICLE, ORGANIZATION, OTHER
    total_events: int = 0
    as_actor_count: int = 0
    as_target_count: int = 0
    connected_entities: Set[str] = field(default_factory=set)
    event_types: Set[str] = field(default_factory=set)
    locations: Set[str] = field(default_factory=set)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "category": self.category,
            "total_events": self.total_events,
            "as_actor_count": self.as_actor_count,
            "as_target_count": self.as_target_count,
            "unique_connections_count": len(self.connected_entities),
            "connected_entities": sorted(list(self.connected_entities)),
            "event_types": sorted(list(self.event_types)),
            "locations": sorted(list(self.locations)),
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class EntityExtractor:
    """
    Extracts and profiles unique entities from normalized Events.
    """

    @classmethod
    def infer_category(cls, identifier: str) -> str:
        """
        Lightweight deterministic heuristic to categorize entity identifiers.
        """
        name = str(identifier).strip()
        name_lower = name.lower()

        if name_lower.startswith("person_") or name_lower.startswith("user_") or name_lower.startswith("suspect_"):
            return "PERSON"
        if name_lower.startswith("phone_") or re.match(r"^\+?[0-9]{10,13}$", name):
            return "PHONE"
        if name_lower.startswith("account_") or name_lower.startswith("acc_") or name_lower.startswith("wallet_"):
            return "ACCOUNT"
        if name_lower.startswith("tower_") or name_lower.startswith("loc_") or name_lower.startswith("location_") or name in ["Delhi", "Noida", "Gurgaon", "Mumbai", "Bangalore"]:
            return "LOCATION"
        if name_lower.startswith("veh_") or name_lower.startswith("vehicle_") or name_lower.startswith("car_"):
            return "VEHICLE"
        if name_lower.startswith("org_") or name_lower.startswith("company_") or name_lower.startswith("bank_"):
            return "ORGANIZATION"

        return "OTHER"

    @classmethod
    def extract_profiles(cls, events: List[Event]) -> Dict[str, EntityProfile]:
        """
        Extract unique entity profiles and aggregate event statistics across the dataset.
        """
        profiles: Dict[str, EntityProfile] = {}

        for event in events:
            # Entities to process in this event
            participants = []
            if event.actor and event.actor != "UNKNOWN":
                participants.append((event.actor, True))
            if event.target and event.target != "UNKNOWN":
                participants.append((event.target, False))

            for ent_id, is_actor in participants:
                if ent_id not in profiles:
                    cat = cls.infer_category(ent_id)
                    profiles[ent_id] = EntityProfile(entity_id=ent_id, category=cat)

                prof = profiles[ent_id]
                prof.total_events += 1
                if is_actor:
                    prof.as_actor_count += 1
                    if event.target and event.target != "UNKNOWN" and event.target != ent_id:
                        prof.connected_entities.add(event.target)
                else:
                    prof.as_target_count += 1
                    if event.actor and event.actor != "UNKNOWN" and event.actor != ent_id:
                        prof.connected_entities.add(event.actor)

                prof.event_types.add(event.event_type)
                if event.location:
                    prof.locations.add(event.location)

                if prof.first_seen is None or event.timestamp < prof.first_seen:
                    prof.first_seen = event.timestamp
                if prof.last_seen is None or event.timestamp > prof.last_seen:
                    prof.last_seen = event.timestamp

        return profiles
