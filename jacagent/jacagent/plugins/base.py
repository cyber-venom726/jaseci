"""Base plugin class for JacAgent framework."""

import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from jacagent.exceptions import PluginError
from jacagent.plugins.hooks import HookManager, HookPriority, get_hook_manager


class PluginMetadata(BaseModel):
    """Metadata for a plugin."""
    name: str
    version: str
    description: str
    author: str
    homepage: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    hooks: List[str] = Field(default_factory=list)
    configuration_schema: Optional[Dict[str, Any]] = None


class BasePlugin(ABC):
    """Base class for all JacAgent plugins."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._is_enabled = False
        self._hook_manager = get_hook_manager()
        self._registered_hooks: Set[str] = set()
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        pass
    
    @property
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._is_enabled
    
    async def enable(self) -> None:
        """Enable the plugin."""
        if self._is_enabled:
            return
        
        try:
            await self.on_enable()
            self._register_hooks()
            self._is_enabled = True
        except Exception as e:
            raise PluginError(f"Failed to enable plugin {self.metadata.name}: {e}")
    
    async def disable(self) -> None:
        """Disable the plugin."""
        if not self._is_enabled:
            return
        
        try:
            await self.on_disable()
            self._unregister_hooks()
            self._is_enabled = False
        except Exception as e:
            raise PluginError(f"Failed to disable plugin {self.metadata.name}: {e}")
    
    async def on_enable(self) -> None:
        """Called when plugin is enabled. Override in subclasses."""
        pass
    
    async def on_disable(self) -> None:
        """Called when plugin is disabled. Override in subclasses."""
        pass
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the plugin."""
        self.config.update(config)
        self.on_configure(config)
    
    def on_configure(self, config: Dict[str, Any]) -> None:
        """Called when plugin is configured. Override in subclasses."""
        pass
    
    def _register_hooks(self) -> None:
        """Register all hook methods in this plugin."""
        for method_name in dir(self):
            method = getattr(self, method_name)
            
            # Check if method has hook metadata
            if hasattr(method, '_hook_name'):
                hook_name = method._hook_name
                priority = getattr(method, '_hook_priority', HookPriority.NORMAL)
                
                self._hook_manager.register_hook(
                    hook_name=hook_name,
                    plugin_name=self.metadata.name,
                    func=method,
                    priority=priority
                )
                self._registered_hooks.add(hook_name)
    
    def _unregister_hooks(self) -> None:
        """Unregister all hooks for this plugin."""
        self._hook_manager.unregister_plugin_hooks(self.metadata.name)
        self._registered_hooks.clear()
    
    def get_configuration_schema(self) -> Optional[Dict[str, Any]]:
        """Get the configuration schema for this plugin."""
        return self.metadata.configuration_schema
    
    def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        schema = self.get_configuration_schema()
        if not schema:
            return True
        
        # Basic validation - could use jsonschema for more sophisticated validation
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in config:
                raise PluginError(f"Required configuration field '{field}' missing for plugin {self.metadata.name}")
        
        return True
    
    def __str__(self) -> str:
        return f"{self.metadata.name} v{self.metadata.version}"
    
    def __repr__(self) -> str:
        return f"<Plugin: {self.metadata.name} v{self.metadata.version} enabled={self._is_enabled}>"


class LifecyclePlugin(BasePlugin):
    """Plugin that hooks into agent/mission lifecycle events."""
    
    async def before_agent_init(self, agent_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Called before agent initialization."""
        return agent_config
    
    async def after_agent_init(self, agent: Any, context: Dict[str, Any]) -> None:
        """Called after agent initialization."""
        pass
    
    async def before_mission_start(self, mission: Any, context: Dict[str, Any]) -> Any:
        """Called before mission starts."""
        return mission
    
    async def after_mission_complete(self, mission: Any, result: Any, context: Dict[str, Any]) -> Any:
        """Called after mission completion."""
        return result


class LLMPlugin(BasePlugin):
    """Plugin that hooks into LLM operations."""
    
    async def before_llm_call(self, provider: str, messages: List[Dict], config: Dict, context: Dict) -> Dict:
        """Called before LLM API call."""
        return {"messages": messages, "config": config}
    
    async def after_llm_call(self, provider: str, response: Any, context: Dict) -> Any:
        """Called after LLM API call."""
        return response


class MemoryPlugin(BasePlugin):
    """Plugin that hooks into memory operations."""
    
    async def before_memory_store(self, key: str, value: Any, context: Dict) -> tuple:
        """Called before storing in memory."""
        return (key, value)
    
    async def after_memory_store(self, key: str, value: Any, context: Dict) -> None:
        """Called after storing in memory."""
        pass
    
    async def before_memory_retrieve(self, key: str, context: Dict) -> str:
        """Called before memory retrieval."""
        return key
    
    async def after_memory_retrieve(self, key: str, value: Any, context: Dict) -> Any:
        """Called after memory retrieval."""
        return value


class ToolPlugin(BasePlugin):
    """Plugin that hooks into tool operations."""
    
    async def before_tool_execute(self, tool: Any, args: tuple, kwargs: Dict, context: Dict) -> tuple:
        """Called before tool execution."""
        return (args, kwargs)
    
    async def after_tool_execute(self, tool: Any, result: Any, context: Dict) -> Any:
        """Called after tool execution."""
        return result


class SecurityPlugin(BasePlugin):
    """Plugin that provides security features."""
    
    async def validate_input(self, input_data: Any, context: Dict) -> bool:
        """Validate input data."""
        return True
    
    async def filter_output(self, output_data: Any, context: Dict) -> Any:
        """Filter output data."""
        return output_data
