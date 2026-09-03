"""
Network Graph analysis and visualization helper for DroidLens.
Builds NetworkX graphs, calculates centrality metrics, and prepares Plotly rendering data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import networkx as nx
from ..normalization.schema import Event
from ..entities.extractor import EntityProfile, EntityExtractor
from ..detection.risk_engine import RiskAssessment, EntityRiskAssessment


@dataclass
class GraphData:
    """
    Prepared graph representation ready for interactive Plotly or UI rendering.
    """
    node_x: List[float] = field(default_factory=list)
    node_y: List[float] = field(default_factory=list)
    node_text: List[str] = field(default_factory=list)
    node_ids: List[str] = field(default_factory=list)
    node_categories: List[str] = field(default_factory=list)
    node_colors: List[str] = field(default_factory=list)
    node_sizes: List[int] = field(default_factory=list)
    node_hover_info: List[str] = field(default_factory=list)
    
    edge_x: List[Optional[float]] = field(default_factory=list)
    edge_y: List[Optional[float]] = field(default_factory=list)
    edge_text: List[str] = field(default_factory=list)
    edge_hover_info: List[str] = field(default_factory=list)


class NetworkGraphBuilder:
    """
    Constructs and analyzes entity relationship graphs using NetworkX.
    """

    CATEGORY_COLORS = {
        "PERSON": "#1f77b4",       # Blue
        "PHONE": "#2ca02c",        # Green
        "ACCOUNT": "#ff7f0e",      # Orange
        "LOCATION": "#d62728",     # Red
        "VEHICLE": "#9467bd",      # Purple
        "ORGANIZATION": "#8c564b", # Brown
        "OTHER": "#7f7f7f",        # Grey
    }

    RISK_BORDER_COLORS = {
        "CRITICAL": "#e74c3c",     # Strong Red
        "HIGH": "#e67e22",         # Strong Orange
        "MEDIUM": "#f1c40f",       # Yellow
        "LOW": "#2ecc71",          # Green
    }

    @classmethod
    def build_graph(
        cls,
        events: List[Event],
        profiles: Optional[Dict[str, EntityProfile]] = None,
        event_risks: Optional[Dict[str, RiskAssessment]] = None,
        entity_risks: Optional[Dict[str, EntityRiskAssessment]] = None,
    ) -> nx.Graph:
        """
        Builds a NetworkX graph where nodes are entities and edges represent interactions.
        """
        if profiles is None:
            profiles = EntityExtractor.extract_profiles(events)

        G = nx.Graph()

        # Add Nodes with attributes
        for ent_id, prof in profiles.items():
            e_risk = entity_risks.get(ent_id) if entity_risks else None
            risk_score = e_risk.risk_score if e_risk else 0
            risk_level = e_risk.risk_level if e_risk else "LOW"

            G.add_node(
                ent_id,
                category=prof.category,
                total_events=prof.total_events,
                risk_score=risk_score,
                risk_level=risk_level,
                key_findings=e_risk.key_findings if e_risk else [],
                first_seen=prof.first_seen.isoformat() if prof.first_seen else None,
                last_seen=prof.last_seen.isoformat() if prof.last_seen else None,
            )

        # Add / Aggregate Edges
        for ev in events:
            if not ev.actor or not ev.target or ev.actor == "UNKNOWN" or ev.target == "UNKNOWN" or ev.actor == ev.target:
                continue

            u, v = ev.actor, ev.target
            ev_risk = event_risks.get(ev.event_id).risk_score if (event_risks and ev.event_id in event_risks) else 0

            if G.has_edge(u, v):
                edge_data = G[u][v]
                edge_data["weight"] += 1
                edge_data["event_types"].add(ev.event_type)
                edge_data["events"].append(ev.event_id)
                edge_data["max_risk"] = max(edge_data["max_risk"], ev_risk)
            else:
                G.add_edge(
                    u,
                    v,
                    weight=1,
                    event_types={ev.event_type},
                    events=[ev.event_id],
                    max_risk=ev_risk,
                )

        # Compute centrality metrics
        if len(G.nodes) > 0:
            deg_centrality = nx.degree_centrality(G)
            nx.set_node_attributes(G, deg_centrality, "degree_centrality")
            try:
                betweenness = nx.betweenness_centrality(G)
                nx.set_node_attributes(G, betweenness, "betweenness_centrality")
            except Exception:
                pass

        return G

    @classmethod
    def get_key_entities(cls, G: nx.Graph, top_n: int = 5) -> List[Dict]:
        """
        Identify key/highly connected or high-risk entities.
        """
        entities = []
        for node, attrs in G.nodes(data=True):
            degree = G.degree[node]
            deg_cent = attrs.get("degree_centrality", 0.0)
            betweenness = attrs.get("betweenness_centrality", 0.0)
            risk_score = attrs.get("risk_score", 0)

            # Composite significance score (connectivity + risk)
            significance = (deg_cent * 50) + (betweenness * 30) + (risk_score * 0.5)

            entities.append({
                "entity_id": node,
                "category": attrs.get("category", "OTHER"),
                "degree": degree,
                "degree_centrality": round(deg_cent, 3),
                "betweenness_centrality": round(betweenness, 3),
                "risk_score": risk_score,
                "risk_level": attrs.get("risk_level", "LOW"),
                "significance_score": round(significance, 2),
                "key_findings": attrs.get("key_findings", []),
            })

        entities.sort(key=lambda x: (x["risk_score"], x["degree"], x["significance_score"]), reverse=True)
        return entities[:top_n]

    @classmethod
    def generate_plot_data(cls, G: nx.Graph, selected_entity: Optional[str] = None) -> GraphData:
        """
        Generate (x, y) coordinates and layout structures for Plotly figure rendering.
        """
        if len(G.nodes) == 0:
            return GraphData()

        # Generate spring layout positions
        pos = nx.spring_layout(G, seed=42, k=0.6, iterations=50)

        graph_data = GraphData()

        # 1. Prepare Edge coordinates
        for u, v, data in G.edges(data=True):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            graph_data.edge_x.extend([x0, x1, None])
            graph_data.edge_y.extend([y0, y1, None])

            types_str = ", ".join(data.get("event_types", []))
            weight = data.get("weight", 1)
            max_risk = data.get("max_risk", 0)
            hover = f"Link: {u} ↔ {v}<br>Interactions: {weight}<br>Types: {types_str}<br>Peak Event Risk: {max_risk}"
            graph_data.edge_hover_info.append(hover)

        # 2. Prepare Node coordinates and styling
        for node, attrs in G.nodes(data=True):
            x, y = pos[node]
            graph_data.node_x.append(x)
            graph_data.node_y.append(y)
            graph_data.node_ids.append(node)
            
            cat = attrs.get("category", "OTHER")
            graph_data.node_categories.append(cat)
            
            risk_score = attrs.get("risk_score", 0)
            risk_lvl = attrs.get("risk_level", "LOW")
            degree = G.degree[node]

            # Base color from category
            base_color = cls.CATEGORY_COLORS.get(cat, "#7f7f7f")
            
            # Node size scaled by degree and risk
            size = max(18, min(45, 16 + (degree * 3) + int(risk_score * 0.15)))
            if selected_entity and node == selected_entity:
                size += 10

            graph_data.node_colors.append(base_color)
            graph_data.node_sizes.append(size)

            label = f"{node} ({cat})"
            graph_data.node_text.append(node)

            hover = (
                f"<b>{node}</b> [{cat}]<br>"
                f"Risk Score: <b>{risk_score}/100</b> ({risk_lvl})<br>"
                f"Connections: {degree}<br>"
                f"Total Events: {attrs.get('total_events', 0)}<br>"
            )
            findings = attrs.get("key_findings", [])
            if findings:
                hover += "<br><b>Findings:</b><br>• " + "<br>• ".join(findings[:2])

            graph_data.node_hover_info.append(hover)

        return graph_data
