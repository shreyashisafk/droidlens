"""
Explainable Risk Engine for DroidLens.
Aggregates rule evaluations into bounded 0-100 scores with transparent explanations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from ..normalization.schema import Event
from ..entities.extractor import EntityProfile, EntityExtractor
from .rules import (
    BaseRule,
    RuleCommunicationBurst,
    RuleHighConnectivity,
    RuleTemporalAnomaly,
    RuleUnusualMovement,
    RuleHighValueTransaction,
)


@dataclass
class RiskAssessment:
    """
    Risk assessment result for an individual event.
    """
    event_id: str
    risk_score: int  # 0 to 100
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    reasons: List[str] = field(default_factory=list)
    triggered_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "reasons": self.reasons,
            "triggered_rules": self.triggered_rules,
        }


@dataclass
class EntityRiskAssessment:
    """
    Aggregated risk profile for a specific entity.
    """
    entity_id: str
    risk_score: int
    risk_level: str
    key_findings: List[str] = field(default_factory=list)
    flagged_events_count: int = 0
    total_events_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "key_findings": self.key_findings,
            "flagged_events_count": self.flagged_events_count,
            "total_events_count": self.total_events_count,
        }


class RiskEngine:
    """
    Coordinates detection rules and computes explainable risk assessments.
    """

    def __init__(self, rules: Optional[List[BaseRule]] = None):
        if rules is None:
            self.rules: List[BaseRule] = [
                RuleCommunicationBurst(),
                RuleHighConnectivity(),
                RuleTemporalAnomaly(),
                RuleUnusualMovement(),
                RuleHighValueTransaction(),
            ]
        else:
            self.rules = rules

    @staticmethod
    def _score_to_level(score: int) -> str:
        if score >= 80:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 30:
            return "MEDIUM"
        return "LOW"

    def assess_events(
        self, events: List[Event], profiles: Optional[Dict[str, EntityProfile]] = None
    ) -> Dict[str, RiskAssessment]:
        """
        Evaluate all rules against events and compute risk assessments per event.
        """
        if profiles is None:
            profiles = EntityExtractor.extract_profiles(events)

        event_rule_results: Dict[str, Dict[str, List[str]]] = {e.event_id: {} for e in events}
        event_score_deltas: Dict[str, int] = {e.event_id: 0 for e in events}

        # Run each rule
        for rule in self.rules:
            findings = rule.evaluate_events(events, profiles)
            for eid, r_results in findings.items():
                if eid not in event_score_deltas:
                    event_score_deltas[eid] = 0
                    event_rule_results[eid] = {}

                for r in r_results:
                    event_score_deltas[eid] += r.score_delta
                    if r.rule_name not in event_rule_results[eid]:
                        event_rule_results[eid][r.rule_name] = []
                    event_rule_results[eid][r.rule_name].append(r.reason)

        assessments: Dict[str, RiskAssessment] = {}
        for ev in events:
            eid = ev.event_id
            raw_score = event_score_deltas.get(eid, 0)
            capped_score = min(100, max(0, raw_score))
            level = self._score_to_level(capped_score)

            reasons: List[str] = []
            rules_triggered: List[str] = []
            for rname, r_reasons in event_rule_results.get(eid, {}).items():
                rules_triggered.append(rname)
                for r in r_reasons:
                    if r not in reasons:
                        reasons.append(r)

            assessments[eid] = RiskAssessment(
                event_id=eid,
                risk_score=capped_score,
                risk_level=level,
                reasons=reasons,
                triggered_rules=rules_triggered
            )

        return assessments

    def assess_entities(
        self,
        events: List[Event],
        event_assessments: Dict[str, RiskAssessment],
        profiles: Optional[Dict[str, EntityProfile]] = None
    ) -> Dict[str, EntityRiskAssessment]:
        """
        Aggregate risk assessments across events to compute entity-level risk profiles.
        """
        if profiles is None:
            profiles = EntityExtractor.extract_profiles(events)

        entity_assessments: Dict[str, EntityRiskAssessment] = {}

        for ent_id, prof in profiles.items():
            # Find all events involving this entity
            ent_events = [e for e in events if e.actor == ent_id or e.target == ent_id]
            flagged = [e for e in ent_events if event_assessments.get(e.event_id, RiskAssessment(e.event_id, 0, "LOW")).risk_score >= 30]

            findings: List[str] = []
            score_acc = 0

            # Connectivity factor
            if len(prof.connected_entities) >= 4:
                findings.append(f"Entity is a high-connectivity hub with {len(prof.connected_entities)} unique associates")
                score_acc += 20

            # Flagged events impact
            if flagged:
                max_event_score = max(event_assessments[e.event_id].risk_score for e in flagged)
                score_acc = max(score_acc, max_event_score)
                findings.append(f"Involved in {len(flagged)} flagged/suspicious incident events")

                # Collect distinct reasons
                distinct_reasons = set()
                for e in flagged:
                    for r in event_assessments[e.event_id].reasons:
                        distinct_reasons.add(r)
                for r in list(distinct_reasons)[:3]:
                    findings.append(f"Pattern: {r}")

            final_score = min(100, max(0, score_acc))
            level = self._score_to_level(final_score)

            entity_assessments[ent_id] = EntityRiskAssessment(
                entity_id=ent_id,
                risk_score=final_score,
                risk_level=level,
                key_findings=findings,
                flagged_events_count=len(flagged),
                total_events_count=len(ent_events)
            )

        return entity_assessments
