"""
Modular detection rules for DroidLens.
Each rule evaluates events or entity behavior and outputs explainable triggers.
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Dict, List, Optional
from ..normalization.schema import Event
from ..entities.extractor import EntityProfile


class RuleResult:
    """
    Result emitted by an evaluated rule.
    """
    def __init__(self, rule_name: str, score_delta: int, reason: str, metadata: Optional[Dict] = None):
        self.rule_name = rule_name
        self.score_delta = score_delta
        self.reason = reason
        self.metadata = metadata or {}


class BaseRule(ABC):
    """
    Abstract base class for all detection rules.
    """
    def __init__(self, name: str, weight: int = 25):
        self.name = name
        self.weight = weight

    @abstractmethod
    def evaluate_events(self, events: List[Event], profiles: Dict[str, EntityProfile]) -> Dict[str, List[RuleResult]]:
        """
        Evaluates events and returns a mapping of event_id -> List[RuleResult].
        """
        pass


class RuleCommunicationBurst(BaseRule):
    """
    Rule 1: Flags bursts of communication between actors within a rolling window.
    """
    def __init__(self, time_window_minutes: int = 45, burst_threshold: int = 5, weight: int = 35):
        super().__init__("CommunicationBurst", weight)
        self.window = timedelta(minutes=time_window_minutes)
        self.threshold = burst_threshold

    def evaluate_events(self, events: List[Event], profiles: Dict[str, EntityProfile]) -> Dict[str, List[RuleResult]]:
        results: Dict[str, List[RuleResult]] = {}
        comm_events = [e for e in events if e.event_type in ["CALL", "MESSAGE"]]

        for i, ev in enumerate(comm_events):
            # Check window around this event
            window_start = ev.timestamp - self.window
            window_end = ev.timestamp + self.window

            # Events involving same actor or pair within window
            matching = [
                e for e in comm_events
                if window_start <= e.timestamp <= window_end
                and (e.actor == ev.actor or (e.actor == ev.target and e.target == ev.actor))
            ]

            if len(matching) >= self.threshold:
                if ev.event_id not in results:
                    results[ev.event_id] = []
                results[ev.event_id].append(
                    RuleResult(
                        rule_name=self.name,
                        score_delta=self.weight,
                        reason=f"High-frequency communication burst ({len(matching)} communications involving {ev.actor} within {int(self.window.total_seconds() / 60)} minutes)",
                        metadata={"burst_count": len(matching)}
                    )
                )
        return results


class RuleHighConnectivity(BaseRule):
    """
    Rule 2: Flags events involving entities connected to an unusually high number of unique targets.
    """
    def __init__(self, connectivity_threshold: int = 4, weight: int = 25):
        super().__init__("HighConnectivity", weight)
        self.threshold = connectivity_threshold

    def evaluate_events(self, events: List[Event], profiles: Dict[str, EntityProfile]) -> Dict[str, List[RuleResult]]:
        results: Dict[str, List[RuleResult]] = {}
        for ev in events:
            reasons = []
            for participant in [ev.actor, ev.target]:
                if participant in profiles and len(profiles[participant].connected_entities) >= self.threshold:
                    conn_count = len(profiles[participant].connected_entities)
                    reasons.append(f"{participant} is a high-connectivity hub ({conn_count} unique associated entities)")

            if reasons:
                if ev.event_id not in results:
                    results[ev.event_id] = []
                results[ev.event_id].append(
                    RuleResult(
                        rule_name=self.name,
                        score_delta=self.weight,
                        reason="; ".join(reasons),
                        metadata={"connectivity": self.threshold}
                    )
                )
        return results


class RuleTemporalAnomaly(BaseRule):
    """
    Rule 3: Flags multi-hop chained activity occurring in rapid sequence (e.g. A->B then B->C).
    """
    def __init__(self, max_chain_gap_minutes: int = 20, weight: int = 30):
        super().__init__("TemporalAnomaly", weight)
        self.max_gap = timedelta(minutes=max_chain_gap_minutes)

    def evaluate_events(self, events: List[Event], profiles: Dict[str, EntityProfile]) -> Dict[str, List[RuleResult]]:
        results: Dict[str, List[RuleResult]] = {}

        for i in range(len(events)):
            curr = events[i]
            # Look forward for rapid chained hops (curr.target becomes next.actor)
            for j in range(i + 1, min(i + 8, len(events))):
                nxt = events[j]
                gap = nxt.timestamp - curr.timestamp
                if gap > self.max_gap:
                    break

                if curr.target and curr.target != "UNKNOWN" and curr.target == nxt.actor and nxt.target != curr.actor:
                    # Valid rapid relay chain!
                    reason_curr = f"Rapid sequential relay: {curr.actor} contacted {curr.target}, who then initiated {nxt.event_type} to {nxt.target} within {int(gap.total_seconds() / 60)} minutes"
                    reason_nxt = f"Follow-up relay in rapid sequence from previous event by {curr.actor} ({int(gap.total_seconds() / 60)} min gap)"

                    for eid, rsn in [(curr.event_id, reason_curr), (nxt.event_id, reason_nxt)]:
                        if eid not in results:
                            results[eid] = []
                        results[eid].append(
                            RuleResult(
                                rule_name=self.name,
                                score_delta=self.weight,
                                reason=rsn,
                                metadata={"lead_actor": curr.actor, "relay_actor": curr.target, "dest_actor": nxt.target}
                            )
                        )
        return results


class RuleUnusualMovement(BaseRule):
    """
    Rule 4: Flags rapid geographic displacement between different distant locations.
    """
    def __init__(self, time_window_minutes: int = 60, weight: int = 40):
        super().__init__("UnusualMovement", weight)
        self.window = timedelta(minutes=time_window_minutes)

    def evaluate_events(self, events: List[Event], profiles: Dict[str, EntityProfile]) -> Dict[str, List[RuleResult]]:
        results: Dict[str, List[RuleResult]] = {}

        # Group location-bearing events by entity
        entity_locations: Dict[str, List[Event]] = {}
        for ev in events:
            if ev.location and ev.location != "Unknown":
                ent = ev.actor
                if ent not in entity_locations:
                    entity_locations[ent] = []
                entity_locations[ent].append(ev)

        for ent, loc_events in entity_locations.items():
            for i in range(len(loc_events) - 1):
                e1 = loc_events[i]
                e2 = loc_events[i + 1]
                if e1.location != e2.location:
                    gap = e2.timestamp - e1.timestamp
                    if gap <= self.window:
                        reason = f"Unusual spatial movement: {ent} reported at {e1.location} and {e2.location} within {int(gap.total_seconds() / 60)} minutes (potential physical anomaly/multi-device use)"
                        for eid in [e1.event_id, e2.event_id]:
                            if eid not in results:
                                results[eid] = []
                            results[eid].append(
                                RuleResult(
                                    rule_name=self.name,
                                    score_delta=self.weight,
                                    reason=reason,
                                    metadata={"from_loc": e1.location, "to_loc": e2.location, "gap_minutes": int(gap.total_seconds() / 60)}
                                )
                            )
        return results


class RuleHighValueTransaction(BaseRule):
    """
    Bonus Rule: Flags high-value financial transactions.
    """
    def __init__(self, threshold_amount: float = 100000.0, weight: int = 25):
        super().__init__("HighValueTransaction", weight)
        self.threshold = threshold_amount

    def evaluate_events(self, events: List[Event], profiles: Dict[str, EntityProfile]) -> Dict[str, List[RuleResult]]:
        results: Dict[str, List[RuleResult]] = {}
        for ev in events:
            if ev.event_type == "TRANSACTION":
                amt = ev.metadata.get("amount")
                if amt is not None:
                    try:
                        amt_val = float(amt)
                        if amt_val >= self.threshold:
                            if ev.event_id not in results:
                                results[ev.event_id] = []
                            results[ev.event_id].append(
                                RuleResult(
                                    rule_name=self.name,
                                    score_delta=self.weight,
                                    reason=f"High-value financial transaction detected (Amount: Rs. {amt_val:,.2f})",
                                    metadata={"amount": amt_val}
                                )
                            )
                    except (ValueError, TypeError):
                        pass
        return results
