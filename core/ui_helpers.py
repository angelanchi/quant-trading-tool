# -*- coding: utf-8 -*-
"""
Shared UI helpers for all pages.

Usage (at top of each page, right after st.set_page_config):
    from core.ui_helpers import apply_default_styles
    apply_default_styles()
"""

import streamlit as st


def apply_default_styles():
    """Apply global CSS defaults."""
    pass  # removed: zoom/transform CSS broke Streamlit rendering
