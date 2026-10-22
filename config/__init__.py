# -*- coding: utf-8 -*-
"""
Configuration module.

This module handles application settings and environment variables.
"""

from .settings import Settings, get_settings

__all__ = [
    'Settings',
    'get_settings',
]
