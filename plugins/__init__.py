"""JARVIS NEXUS plugins package."""

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION, execute, get_tools

__all__ = [
    "PLUGIN_NAME",
    "PLUGIN_DESCRIPTION",
    "PLUGIN_VERSION",
    "get_tools",
    "execute",
]
