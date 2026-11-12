"""Placeholder pages for later M5 milestones."""
from __future__ import annotations

import streamlit as st


def _placeholder(title: str, question: str, evidence: str, planned: str, scope: str) -> None:
    st.title(title)
    st.caption(f"Evidence type: {evidence}")
    st.info(f"Planned for {planned}. This page is not implemented yet.")
    st.markdown(f"**Question this page will answer:** {question}")
    st.markdown(f"**Planned scope:** {scope}")


def render_targeting_explorer() -> None:
    _placeholder(
        "Targeting Explorer",
        "What would historical targeting lists have captured at 5%, 10% and 20% capacity?",
        "Retrospective targeting — not causal campaign impact",
        "a later M5 milestone (proposed M5-004)",
        "Aggregate M3 precision, capture, lift and overlap for Model C, RFM, frequency and random "
        "expectation, including the frequency tie-break disclosure. No customer lists.",
    )


def render_experiment_feasibility() -> None:
    _placeholder(
        "Experiment Feasibility",
        "What sample size and economics might a future randomised CRM pilot need?",
        "Hypothetical scenario",
        "a later M5 milestone (proposed M5-005)",
        "Interactive inputs wired to the existing M4 scenario functions; every input labelled as an assumption.",
    )
