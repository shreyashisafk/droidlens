"""
DroidLens — Streamlit Investigator Dashboard.
Interactive visual forensic triage and criminal network intelligence system.
"""

from datetime import datetime
from pathlib import Path
import sys

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.pipeline import DroidLensPipeline, PipelineResult
from src.correlation.graph import NetworkGraphBuilder


# Page Configuration
st.set_page_config(
    page_title="DroidLens | Investigation Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-top: -5px;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
    }
    .badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-high {
        background-color: #FFEDD5;
        color: #9A3412;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-medium {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-low {
        background-color: #DCFCE7;
        color: #166534;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)


def create_plotly_network_figure(result: PipelineResult, selected_entity: str = "All") -> go.Figure:
    """
    Build an interactive Plotly graph figure from the pipeline's NetworkX graph data.
    """
    plot_data = NetworkGraphBuilder.generate_plot_data(
        result.graph,
        selected_entity=None if selected_entity == "All" else selected_entity
    )

    # Edge Traces
    edge_trace = go.Scatter(
        x=plot_data.edge_x,
        y=plot_data.edge_y,
        line=dict(width=1.5, color="#94A3B8"),
        hoverinfo="none",
        mode="lines"
    )

    # Node Traces
    node_trace = go.Scatter(
        x=plot_data.node_x,
        y=plot_data.node_y,
        mode="markers+text",
        hoverinfo="text",
        text=plot_data.node_text,
        textposition="top center",
        textfont=dict(size=11, color="#1E293B", family="sans-serif"),
        hovertext=plot_data.node_hover_info,
        marker=dict(
            showscale=False,
            color=plot_data.node_colors,
            size=plot_data.node_sizes,
            line=dict(width=2, color="#0F172A")
        )
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title=dict(
                text=f"<b>Entity Interaction & Correlation Network</b> (Displaying {len(plot_data.node_ids)} Entities)",
                font=dict(size=16)
            ),
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=20, r=20, t=45),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            height=540,
        )
    )
    return fig


def main():
    # Header Banner
    st.markdown('<p class="main-title">DROIDLENS — Investigation Intelligence</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">AI-Powered Forensic Triage & Criminal Network Analysis System | <i>SIH 2026 Problem ID: 26189</i></p>',
        unsafe_allow_html=True
    )

    st.info(
        "💡 **Investigator Notice:** DroidLens is an explainable decision-support triage system designed to highlight "
        "suspicious patterns and link fragmented records for human review. It does not make autonomous determinations of guilt.",
        icon="ℹ️"
    )

    # Sidebar Controls
    st.sidebar.header("📁 Data Ingestion & Settings")
    data_source_mode = st.sidebar.radio(
        "Select Data Source",
        ["Use Synthetic Demo Dataset (CSV)", "Use Synthetic Demo Dataset (JSON)", "Upload Custom Dataset (CSV/JSON)"],
        index=0
    )

    raw_file = None
    file_format = "csv"
    sample_dir = root_dir / "data" / "raw"

    if data_source_mode == "Use Synthetic Demo Dataset (CSV)":
        raw_file = sample_dir / "synthetic_investigation.csv"
        file_format = "csv"
    elif data_source_mode == "Use Synthetic Demo Dataset (JSON)":
        raw_file = sample_dir / "synthetic_investigation.json"
        file_format = "json"
    else:
        uploaded = st.sidebar.file_uploader("Upload CSV or JSON dataset", type=["csv", "json"])
        if uploaded is not None:
            raw_file = uploaded
            file_format = "csv" if uploaded.name.endswith(".csv") else "json"

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Analysis Parameters")
    corr_window = st.sidebar.slider("Temporal Correlation Window (mins)", min_value=5, max_value=120, value=30, step=5)
    min_risk_threshold = st.sidebar.slider("Minimum Event Risk Filter", min_value=0, max_value=100, value=0, step=10)

    if raw_file is None:
        st.warning("Please select or upload a dataset to begin investigation analysis.")
        return

    # Run Analysis Pipeline
    pipeline = DroidLensPipeline(correlation_window_minutes=corr_window)
    with st.spinner("Processing event records, extracting entities, evaluating risk rules & building graph..."):
        try:
            result = pipeline.run_from_file(raw_file, file_format=file_format, correlation_window_minutes=corr_window)
        except Exception as e:
            st.error(f"Error processing dataset: {str(e)}")
            return

    # Entity Filter Selector in Sidebar
    all_entity_ids = ["All"] + sorted(list(result.profiles.keys()))
    selected_entity = st.sidebar.selectbox("🎯 Drill-down into Entity", all_entity_ids, index=0)

    # Section 1: Executive KPI Metrics
    st.markdown("### 📊 Investigation Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Events Ingested", result.summary_metrics["total_events"])
    with c2:
        st.metric("Unique Entities", result.summary_metrics["total_entities"])
    with c3:
        st.metric("Flagged Events", result.summary_metrics["flagged_events_count"], delta_color="inverse")
    with c4:
        st.metric("Incident Clusters", result.summary_metrics["incident_clusters_count"])
    with c5:
        st.metric("Relationships Mapped", result.summary_metrics["total_relationships"])

    st.markdown("---")

    # Tabs for structured investigator workflow
    tab_network, tab_entities, tab_timeline, tab_clusters, tab_evidence = st.tabs([
        "🕸️ Network Graph",
        "👤 Key Entities & Drill-down",
        "⏱️ Chronological Timeline",
        "🔗 Correlated Incident Clusters",
        "📋 Suspicious Event Log & Export"
    ])

    # TAB 1: Network Graph
    with tab_network:
        st.subheader("🕸️ Criminal & Interaction Network Analysis")
        col_g, col_legend = st.columns([4, 1])

        with col_g:
            fig = create_plotly_network_figure(result, selected_entity=selected_entity)
            st.plotly_chart(fig, use_container_width=True)

        with col_legend:
            st.markdown("#### Entity Legend")
            for cat, color in NetworkGraphBuilder.CATEGORY_COLORS.items():
                st.markdown(f"<span style='color:{color}; font-weight:bold;'>■</span> {cat}", unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("#### Node Sizing")
            st.caption("Node size is scaled by degree of connectivity and aggregate risk score.")

    # TAB 2: Key Entities & Drill-down
    with tab_entities:
        st.subheader("👤 Key Entities & Risk Profiles")
        
        # Entity cards / table
        key_df_data = []
        for k in result.key_entities:
            key_df_data.append({
                "Entity": k["entity_id"],
                "Category": k["category"],
                "Risk Score": f"{k['risk_score']}/100",
                "Risk Tier": k["risk_level"],
                "Connections (Degree)": k["degree"],
                "Centrality": k["degree_centrality"],
                "Key Finding": k["key_findings"][0] if k["key_findings"] else "Standard activity"
            })
        
        st.dataframe(pd.DataFrame(key_df_data), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("🔍 Entity Inspector")
        inspect_id = st.selectbox("Select entity to inspect detailed dossier:", sorted(list(result.profiles.keys())), index=0)
        
        if inspect_id:
            prof = result.profiles[inspect_id]
            e_risk = result.entity_risks.get(inspect_id)
            
            c_left, c_right = st.columns([1, 2])
            with c_left:
                st.markdown(f"### **{prof.entity_id}**")
                st.markdown(f"**Category:** `{prof.category}`")
                
                score = e_risk.risk_score if e_risk else 0
                lvl = e_risk.risk_level if e_risk else "LOW"
                badge_cls = f"badge-{lvl.lower()}"
                st.markdown(f"**Risk Rating:** <span class='{badge_cls}'>{score}/100 ({lvl})</span>", unsafe_allow_html=True)
                st.markdown(f"**Total Events Involved:** `{prof.total_events}`")
                st.markdown(f"**As Actor (Initiator):** `{prof.as_actor_count}` | **As Target:** `{prof.as_target_count}`")
                st.markdown(f"**Unique Associates:** `{len(prof.connected_entities)}`")
                if prof.locations:
                    st.markdown(f"**Locations Visited:** `{', '.join(prof.locations)}`")
                if prof.first_seen and prof.last_seen:
                    st.caption(f"Active between {prof.first_seen.strftime('%H:%M')} and {prof.last_seen.strftime('%H:%M')}")

            with c_right:
                st.markdown("#### 💡 Explainable Risk Findings & Reasons")
                if e_risk and e_risk.key_findings:
                    for find in e_risk.key_findings:
                        st.markdown(f"- ⚠️ {find}")
                else:
                    st.success("No abnormal or high-risk activity detected for this entity.")

                st.markdown("#### 🤝 Associated Entities (1-Hop Neighbors)")
                st.write(", ".join([f"`{a}`" for a in sorted(list(prof.connected_entities))]))

    # TAB 3: Chronological Timeline
    with tab_timeline:
        st.subheader("⏱️ Chronological Investigation Timeline")
        
        t_items = [
            t for t in result.timeline
            if (selected_entity == "All" or selected_entity in [t.actor, t.target])
            and t.risk_score >= min_risk_threshold
        ]

        if not t_items:
            st.info("No events match current filter parameters.")
        else:
            for item in t_items:
                with st.container():
                    col_t1, col_t2, col_t3 = st.columns([1.5, 3.5, 1])
                    with col_t1:
                        st.markdown(f"**`{item.formatted_time}`**")
                        st.caption(f"Type: `{item.event_type}` | Loc: `{item.location}`")
                    with col_t2:
                        st.markdown(f"**{item.action_narrative}**")
                        if item.reasons:
                            for r in item.reasons:
                                st.markdown(f"<small style='color:#B91C1C;'>• {r}</small>", unsafe_allow_html=True)
                    with col_t3:
                        badge_cls = f"badge-{item.risk_level.lower()}"
                        st.markdown(f"<span class='{badge_cls}'>Risk: {item.risk_score}</span>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px dashed #E2E8F0;' />", unsafe_allow_html=True)

    # TAB 4: Correlated Incident Clusters
    with tab_clusters:
        st.subheader("🔗 Correlated Temporal Incident Clusters")
        st.caption(f"Events occurring within a {corr_window}-minute sliding window with overlapping participants.")

        for cluster in result.clusters:
            with st.expander(f"📌 {cluster.cluster_id} — {cluster.summary} (Peak Risk: {cluster.peak_risk_score}/100)", expanded=(cluster.peak_risk_score >= 50)):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.markdown(f"**Time Span:** `{cluster.start_time.strftime('%H:%M:%S')}` to `{cluster.end_time.strftime('%H:%M:%S')}`")
                    st.markdown(f"**Entities Involved:** {', '.join([f'`{e}`' for e in cluster.entities_involved])}")
                with c_b:
                    st.markdown(f"**Locations:** {', '.join([f'`{l}`' for l in cluster.primary_locations]) if cluster.primary_locations else 'N/A'}")
                    st.markdown(f"**Total Events in Cluster:** `{len(cluster.events)}`")

                st.markdown("##### Cluster Events Sequence:")
                cluster_df_rows = []
                for ev in cluster.events:
                    r_item = result.event_risks.get(ev.event_id)
                    cluster_df_rows.append({
                        "Event ID": ev.event_id,
                        "Time": ev.timestamp.strftime("%H:%M:%S"),
                        "Type": ev.event_type,
                        "Actor": ev.actor,
                        "Target": ev.target,
                        "Location": ev.location or "Unknown",
                        "Risk Score": r_item.risk_score if r_item else 0,
                    })
                st.dataframe(pd.DataFrame(cluster_df_rows), use_container_width=True, hide_index=True)

    # TAB 5: Suspicious Event Log & Export
    with tab_evidence:
        st.subheader("📋 Complete Suspicious & Normalized Event Log")

        all_rows = []
        for ev in result.events:
            r_item = result.event_risks.get(ev.event_id)
            if r_item and r_item.risk_score >= min_risk_threshold:
                all_rows.append({
                    "event_id": ev.event_id,
                    "timestamp": ev.timestamp.isoformat(),
                    "event_type": ev.event_type,
                    "actor": ev.actor,
                    "target": ev.target,
                    "location": ev.location or "Unknown",
                    "risk_score": r_item.risk_score,
                    "risk_level": r_item.risk_level,
                    "reasons": " | ".join(r_item.reasons) if r_item.reasons else "Normal",
                    "source": ev.source
                })

        df_export = pd.DataFrame(all_rows)
        st.dataframe(df_export, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("💾 Export Investigation Dossier")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            csv_data = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Evidence Dossier (CSV)",
                data=csv_data,
                file_name=f"droidlens_investigation_dossier_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        with col_d2:
            json_data = df_export.to_json(orient="records", indent=2).encode("utf-8")
            st.download_button(
                label="📥 Download Structured Intelligence (JSON)",
                data=json_data,
                file_name=f"droidlens_investigation_dossier_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )


if __name__ == "__main__":
    main()
