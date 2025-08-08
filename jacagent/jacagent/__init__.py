"""
JacAgent - Next-Generation Agentic Framework

A modern, extensible multi-agent framework with enhanced customization
and comprehensive plugin architecture.
"""

__version__ = "0.1.0"
__author__ = "JacAgent Contributors"
__email__ = "contributors@jacagent.dev"
__license__ = "MIT"

# Core imports
from jacagent.core.agent import Agent
from jacagent.core.squad import Squad
from jacagent.core.mission import Mission
from jacagent.core.llm import LLMProvider, BaseLLM
from jacagent.core.memory import MemoryManager
from jacagent.core.tools import BaseTool, ToolRegistry

# Plugin system
from jacagent.plugins.base import BasePlugin
from jacagent.plugins.registry import PluginRegistry
from jacagent.plugins.hooks import hook, HookManager

# Execution patterns
from jacagent.orchestration.patterns import (
    SequentialPattern,
    ParallelPattern,
    HierarchicalPattern,
    AdaptivePattern,
)

# Configuration
from jacagent.config import JacAgentConfig
from jacagent.exceptions import (
    JacAgentError,
    AgentError,
    MissionError,
    PluginError,
)

# Public API
__all__ = [
    # Core classes
    "Agent",
    "Squad",
    "Mission",
    "LLMProvider",
    "BaseLLM",
    "MemoryManager",
    "BaseTool",
    "ToolRegistry",
    
    # Plugin system
    "BasePlugin",
    "PluginRegistry", 
    "hook",
    "HookManager",
    
    # Orchestration
    "SequentialPattern",
    "ParallelPattern", 
    "HierarchicalPattern",
    "AdaptivePattern",
    
    # Configuration & Exceptions
    "JacAgentConfig",
    "JacAgentError",
    "AgentError",
    "MissionError",
    "PluginError",
    
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
]

# Initialize plugin system on import
_plugin_registry = PluginRegistry()
_hook_manager = HookManager()

def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _plugin_registry

def get_hook_manager() -> HookManager:
    """Get the global hook manager."""
    return _hook_manager

# Auto-discovery of built-in plugins
def _discover_builtin_plugins():
    """Discover and load built-in plugins."""
    import os
    import importlib
    
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins", "builtin")
    if os.path.exists(plugins_dir):
        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = f"jacagent.plugins.builtin.{filename[:-3]}"
                try:
                    importlib.import_module(module_name)
                except ImportError:
                    pass  # Skip failed imports

# Load built-in plugins
_discover_builtin_plugins()
