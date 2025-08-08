"""Plugin system for JacAgent framework."""

from jacagent.plugins.base import BasePlugin
from jacagent.plugins.registry import PluginRegistry
from jacagent.plugins.hooks import hook, HookManager, HookSpec

__all__ = [
    "BasePlugin",
    "PluginRegistry", 
    "hook",
    "HookManager",
    "HookSpec",
]
