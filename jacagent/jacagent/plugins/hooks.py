"""Hook system for JacAgent plugins."""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Union, get_type_hints
from functools import wraps
from pydantic import BaseModel
from enum import Enum

from jacagent.exceptions import PluginError


class HookPriority(int, Enum):
    """Hook execution priority levels."""
    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


class HookSpec(BaseModel):
    """Hook specification defining the interface."""
    name: str
    description: str
    parameters: Dict[str, Any]
    return_type: Optional[Any] = None
    is_async: bool = False
    allow_multiple: bool = True
    priority: HookPriority = HookPriority.NORMAL


class RegisteredHook(BaseModel):
    """Registered hook implementation."""
    name: str
    plugin_name: str
    func: Callable
    priority: HookPriority
    is_async: bool
    
    class Config:
        arbitrary_types_allowed = True


class HookManager:
    """Manages hook registration and execution."""
    
    def __init__(self):
        self._hooks: Dict[str, List[RegisteredHook]] = {}
        self._hook_specs: Dict[str, HookSpec] = {}
        self._initialize_builtin_hooks()
    
    def _initialize_builtin_hooks(self):
        """Initialize built-in hook specifications."""
        builtin_hooks = [
            # Agent lifecycle hooks
            HookSpec(
                name="before_agent_init",
                description="Called before agent initialization",
                parameters={"agent_config": dict, "context": dict},
                return_type=dict,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_agent_init", 
                description="Called after agent initialization",
                parameters={"agent": Any, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="before_agent_execute",
                description="Called before agent execution",
                parameters={"agent": Any, "mission": Any, "context": dict},
                return_type=dict,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_agent_execute",
                description="Called after agent execution", 
                parameters={"agent": Any, "result": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="on_agent_error",
                description="Called when agent encounters error",
                parameters={"agent": Any, "error": Exception, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            
            # Mission lifecycle hooks
            HookSpec(
                name="before_mission_start",
                description="Called before mission starts",
                parameters={"mission": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="during_mission_execute",
                description="Called during mission execution",
                parameters={"mission": Any, "progress": dict, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_mission_complete",
                description="Called after mission completion",
                parameters={"mission": Any, "result": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="on_mission_error", 
                description="Called when mission encounters error",
                parameters={"mission": Any, "error": Exception, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            
            # LLM hooks
            HookSpec(
                name="before_llm_call",
                description="Called before LLM API call",
                parameters={"provider": str, "messages": list, "config": dict, "context": dict},
                return_type=dict,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_llm_call",
                description="Called after LLM API call",
                parameters={"provider": str, "response": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="on_llm_error",
                description="Called when LLM call fails",
                parameters={"provider": str, "error": Exception, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            
            # Memory hooks
            HookSpec(
                name="before_memory_store",
                description="Called before storing in memory", 
                parameters={"key": str, "value": Any, "context": dict},
                return_type=tuple,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_memory_store",
                description="Called after storing in memory",
                parameters={"key": str, "value": Any, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="before_memory_retrieve",
                description="Called before memory retrieval",
                parameters={"key": str, "context": dict},
                return_type=str,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_memory_retrieve",
                description="Called after memory retrieval",
                parameters={"key": str, "value": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            
            # Tool hooks
            HookSpec(
                name="before_tool_execute",
                description="Called before tool execution",
                parameters={"tool": Any, "args": tuple, "kwargs": dict, "context": dict},
                return_type=tuple,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_tool_execute",
                description="Called after tool execution",
                parameters={"tool": Any, "result": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            
            # Squad hooks
            HookSpec(
                name="before_squad_execute",
                description="Called before squad execution",
                parameters={"squad": Any, "context": dict},
                return_type=dict,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="after_squad_execute",
                description="Called after squad execution", 
                parameters={"squad": Any, "result": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
            
            # Configuration hooks
            HookSpec(
                name="on_config_change",
                description="Called when configuration changes",
                parameters={"old_config": dict, "new_config": dict, "context": dict},
                return_type=None,
                is_async=True,
                allow_multiple=True
            ),
            
            # Security hooks
            HookSpec(
                name="validate_input",
                description="Called to validate input",
                parameters={"input_data": Any, "context": dict},
                return_type=bool,
                is_async=True,
                allow_multiple=True
            ),
            HookSpec(
                name="filter_output",
                description="Called to filter output",
                parameters={"output_data": Any, "context": dict},
                return_type=Any,
                is_async=True,
                allow_multiple=True
            ),
        ]
        
        for hook_spec in builtin_hooks:
            self._hook_specs[hook_spec.name] = hook_spec
    
    def register_hook_spec(self, hook_spec: HookSpec) -> None:
        """Register a new hook specification."""
        if hook_spec.name in self._hook_specs:
            raise PluginError(f"Hook specification '{hook_spec.name}' already exists")
        self._hook_specs[hook_spec.name] = hook_spec
    
    def register_hook(
        self,
        hook_name: str,
        plugin_name: str,
        func: Callable,
        priority: HookPriority = HookPriority.NORMAL
    ) -> None:
        """Register a hook implementation."""
        if hook_name not in self._hook_specs:
            raise PluginError(f"Unknown hook: {hook_name}")
        
        hook_spec = self._hook_specs[hook_name]
        is_async = asyncio.iscoroutinefunction(func)
        
        # Validate hook signature
        self._validate_hook_signature(func, hook_spec)
        
        registered_hook = RegisteredHook(
            name=hook_name,
            plugin_name=plugin_name,
            func=func,
            priority=priority,
            is_async=is_async
        )
        
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        
        self._hooks[hook_name].append(registered_hook)
        # Sort by priority
        self._hooks[hook_name].sort(key=lambda h: h.priority.value)
    
    def _validate_hook_signature(self, func: Callable, hook_spec: HookSpec) -> None:
        """Validate that hook function signature matches specification."""
        try:
            sig = inspect.signature(func)
            # Basic validation - could be more sophisticated
            params = list(sig.parameters.keys())
            expected_params = list(hook_spec.parameters.keys())
            
            # Allow extra context parameter
            if 'context' not in params and 'context' in expected_params:
                pass  # Context is optional
            
        except Exception as e:
            raise PluginError(f"Invalid hook signature for {func.__name__}: {e}")
    
    async def call_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """Call all registered hooks for a given hook name."""
        if hook_name not in self._hooks:
            return []
        
        results = []
        context = kwargs.get('context', {})
        
        for registered_hook in self._hooks[hook_name]:
            try:
                if registered_hook.is_async:
                    result = await registered_hook.func(**kwargs)
                else:
                    result = registered_hook.func(**kwargs)
                results.append(result)
                
                # Update kwargs with result if it's a transforming hook
                if result is not None and isinstance(result, dict):
                    kwargs.update(result)
                    
            except Exception as e:
                # Log error but continue with other hooks
                context.setdefault('hook_errors', []).append({
                    'hook_name': hook_name,
                    'plugin_name': registered_hook.plugin_name,
                    'error': str(e)
                })
        
        return results
    
    def call_hook_sync(self, hook_name: str, **kwargs) -> List[Any]:
        """Synchronously call hooks (only non-async ones)."""
        if hook_name not in self._hooks:
            return []
        
        results = []
        context = kwargs.get('context', {})
        
        for registered_hook in self._hooks[hook_name]:
            if registered_hook.is_async:
                continue  # Skip async hooks in sync call
                
            try:
                result = registered_hook.func(**kwargs)
                results.append(result)
                
                # Update kwargs with result if it's a transforming hook
                if result is not None and isinstance(result, dict):
                    kwargs.update(result)
                    
            except Exception as e:
                context.setdefault('hook_errors', []).append({
                    'hook_name': hook_name,
                    'plugin_name': registered_hook.plugin_name,
                    'error': str(e)
                })
        
        return results
    
    def unregister_hook(self, hook_name: str, plugin_name: str) -> None:
        """Unregister a hook implementation."""
        if hook_name in self._hooks:
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name] 
                if h.plugin_name != plugin_name
            ]
    
    def unregister_plugin_hooks(self, plugin_name: str) -> None:
        """Unregister all hooks for a plugin."""
        for hook_name in self._hooks:
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name]
                if h.plugin_name != plugin_name
            ]
    
    def get_hook_specs(self) -> Dict[str, HookSpec]:
        """Get all registered hook specifications."""
        return self._hook_specs.copy()
    
    def get_registered_hooks(self, hook_name: Optional[str] = None) -> Dict[str, List[RegisteredHook]]:
        """Get registered hook implementations."""
        if hook_name:
            return {hook_name: self._hooks.get(hook_name, [])}
        return self._hooks.copy()


# Decorator for registering hooks
def hook(
    hook_name: str, 
    priority: HookPriority = HookPriority.NORMAL,
    plugin_name: Optional[str] = None
):
    """Decorator to register a function as a hook."""
    def decorator(func):
        # Store hook metadata on function
        func._hook_name = hook_name
        func._hook_priority = priority
        func._hook_plugin_name = plugin_name
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


# Global hook manager instance
_global_hook_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    """Get the global hook manager instance."""
    global _global_hook_manager
    if _global_hook_manager is None:
        _global_hook_manager = HookManager()
    return _global_hook_manager
