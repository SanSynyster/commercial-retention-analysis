"""Shared Streamlit page objects for navigation and contextual page links."""
from __future__ import annotations

import streamlit as st

from views.customer_overview import render as render_customer_overview
from views.purchase_propensity import render as render_purchase_propensity
from views.predictive_intelligence import render as render_predictive_intelligence
from views.segmentation_intelligence import render as render_segmentation_intelligence
from views.causal_evidence import render as render_causal_evidence
from views.targeting_explorer import render_targeting_explorer
from views.experiment_feasibility import render as render_experiment_feasibility

CUSTOMER_OVERVIEW_PAGE = st.Page(render_customer_overview, title="Customer Overview", url_path="customer-overview", default=True)
PURCHASE_PROPENSITY_PAGE = st.Page(render_purchase_propensity, title="Purchase Propensity", url_path="purchase-propensity")
PREDICTIVE_INTELLIGENCE_PAGE = st.Page(render_predictive_intelligence, title="Predictive Intelligence", url_path="predictive-intelligence")
SEGMENTATION_INTELLIGENCE_PAGE = st.Page(render_segmentation_intelligence, title="Segmentation Intelligence", url_path="segmentation-intelligence")
CAUSAL_EVIDENCE_PAGE = st.Page(render_causal_evidence, title="Causal Evidence & Experimentation", url_path="causal-evidence")
TARGETING_EXPLORER_PAGE = st.Page(render_targeting_explorer, title="CRM Targeting Explorer", url_path="targeting-explorer")
EXPERIMENT_FEASIBILITY_PAGE = st.Page(render_experiment_feasibility, title="CRM Experiment Feasibility", url_path="experiment-feasibility")

PAGES = [
    CUSTOMER_OVERVIEW_PAGE,
    PURCHASE_PROPENSITY_PAGE,
    PREDICTIVE_INTELLIGENCE_PAGE,
    SEGMENTATION_INTELLIGENCE_PAGE,
    CAUSAL_EVIDENCE_PAGE,
    TARGETING_EXPLORER_PAGE,
    EXPERIMENT_FEASIBILITY_PAGE,
]
