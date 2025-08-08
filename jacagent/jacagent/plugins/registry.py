"""Plugin registry for managing JacAgent plugins."""

import asyncio
import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from jacagent.exceptions import PluginError
from jacagent.plugins.base import BasePlugin, PluginMetadata
from jacagent.config import get_config


class PluginRegistry:
    """Registry for managing plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}
        self._enabled_plugins: Dict[str, BasePlugin] = {}
        self._plugin_directories: List[Path] = []
        self._auto_discovery_enabled = True
    
    def register_plugin_class(self, plugin_class: Type[BasePlugin]) -> None:
        """Register a plugin class."""
        if not issubclass(plugin_class, BasePlugin):
            raise PluginError(f"Plugin class must inherit from BasePlugin: {plugin_class}")
        
        # Create temporary instance to get metadata
        temp_instance = plugin_class()
        metadata = temp_instance.metadata
        
        if metadata.name in self._plugin_classes:
            raise PluginError(f"Plugin '{metadata.name}' is already registered")
        
        self._plugin_classes[metadata.name] = plugin_class
    
    def create_plugin(self, plugin_name: str, config: Optional[Dict[str, Any]] = None) -> BasePlugin:
        """Create a plugin instance."""
        if plugin_name not in self._plugin_classes:
            raise PluginError(f"Unknown plugin: {plugin_name}")
        
        plugin_class = self._plugin_classes[plugin_name]
        plugin_instance = plugin_class(config)
        
        # Validate configuration
        if config:
            plugin_instance.validate_configuration(config)
        
        self._plugins[plugin_name] = plugin_instance
        return plugin_instance
    
    async def enable_plugin(self, plugin_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        """Enable a plugin."""
        if plugin_name in self._enabled_plugins:
            return  # Already enabled
        
        # Create plugin if not exists
        if plugin_name not in self._plugins:
            self.create_plugin(plugin_name, config)
        
        plugin = self._plugins[plugin_name]
        
        # Configure if config provided
        if config:
            plugin.configure(config)
        
        # Check dependencies
        await self._check_dependencies(plugin)
        
        # Enable plugin
        await plugin.enable()
        self._enabled_plugins[plugin_name] = plugin
    
    async def disable_plugin(self, plugin_name: str) -> None:
        """Disable a plugin."""
        if plugin_name not in self._enabled_plugins:
            return  # Not enabled
        
        plugin = self._enabled_plugins[plugin_name]
        await plugin.disable()
        del self._enabled_plugins[plugin_name]
    
    async def _check_dependencies(self, plugin: BasePlugin) -> None:
        """Check if plugin dependencies are satisfied."""
        for dep in plugin.metadata.dependencies:
            if dep not in self._enabled_plugins:
                # Try to enable dependency
                try:
                    await self.enable_plugin(dep)
                except PluginError:
                    raise PluginError(f"Plugin {plugin.metadata.name} requires {dep} but it cannot be enabled")
    
    def discover_plugins(self, directory: Union[str, Path]) -> List[str]:
        """Discover plugins in a directory."""
        directory = Path(directory)
        if not directory.exists():
            return []
        
        discovered = []
        
        # Add directory to Python path temporarily
        original_path = sys.path.copy()
        sys.path.insert(0, str(directory))
        
        try:
            for file_path in directory.glob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                
                module_name = file_path.stem
                try:
                    module = importlib.import_module(module_name)
                    
                    # Look for BasePlugin subclasses
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BasePlugin) and 
                            obj != BasePlugin and 
                            hasattr(obj, 'metadata')):
                            
                            self.register_plugin_class(obj)
                            discovered.append(obj.metadata.property.name if hasattr(obj.metadata, 'property') else name)
                            
                except Exception as e:
                    # Log error but continue discovery
                    print(f"Failed to load plugin from {file_path}: {e}")
                    
        finally:
            # Restore original path
            sys.path = original_path
        
        return discovered
    
    def auto_discover(self) -> List[str]:
        """Auto-discover plugins from configured directories."""
        if not self._auto_discovery_enabled:
            return []
        
        config = get_config()
        discovered = []
        
        # Discover from configured directories
        for directory in config.plugins.plugin_directories:
            discovered.extend(self.discover_plugins(directory))
        
        # Discover from built-in plugins
        builtin_dir = Path(__file__).parent / "builtin"
        if builtin_dir.exists():
            discovered.extend(self.discover_plugins(builtin_dir))
        
        return discovered
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin instance."""
        return self._plugins.get(plugin_name)
    
    def get_enabled_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get an enabled plugin instance."""
        return self._enabled_plugins.get(plugin_name)
    
    def list_available_plugins(self) -> List[str]:
        """List all available plugin names."""
        return list(self._plugin_classes.keys())
    
    def list_enabled_plugins(self) -> List[str]:
        """List all enabled plugin names."""
        return list(self._enabled_plugins.keys())
    
    def get_plugin_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """Get plugin metadata."""
        if plugin_name in self._plugin_classes:
            temp_instance = self._plugin_classes[plugin_name]()
            return temp_instance.metadata
        return None
    
    async def enable_default_plugins(self) -> None:
        """Enable plugins specified in configuration."""
        config = get_config()
        
        # Auto-discover first
        if config.plugins.auto_discover:
            self.auto_discover()
        
        # Enable configured plugins
        for plugin_name in config.plugins.enabled_plugins:
            try:
                await self.enable_plugin(plugin_name)
            except PluginError as e:
                print(f"Failed to enable plugin {plugin_name}: {e}")
    
    async def disable_all_plugins(self) -> None:
        """Disable all enabled plugins."""
        plugin_names = list(self._enabled_plugins.keys())
        for plugin_name in plugin_names:
            await self.disable_plugin(plugin_name)
    
    def set_auto_discovery(self, enabled: bool) -> None:
        """Enable or disable auto-discovery."""
        self._auto_discovery_enabled = enabled
    
    def add_plugin_directory(self, directory: Union[str, Path]) -> None:
        """Add a directory for plugin discovery."""
        directory = Path(directory)
        if directory not in self._plugin_directories:
            self._plugin_directories.append(directory)
    
    def remove_plugin_directory(self, directory: Union[str, Path]) -> None:
        """Remove a directory from plugin discovery."""
        directory = Path(directory)
        if directory in self._plugin_directories:
            self._plugin_directories.remove(directory)
    
    def reload_plugin(self, plugin_name: str) -> None:
        """Reload a plugin (useful for development)."""
        if plugin_name in self._enabled_plugins:
            # Disable first
            asyncio.create_task(self.disable_plugin(plugin_name))
        
        # Remove from registry
        if plugin_name in self._plugin_classes:
            del self._plugin_classes[plugin_name]
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
        
        # Re-discover and enable
        self.auto_discover()
        if plugin_name in self._plugin_classes:
            asyncio.create_task(self.enable_plugin(plugin_name))


# Global plugin registry instance
_global_plugin_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry instance."""
    global _global_plugin_registry
    if _global_plugin_registry is None:
        _global_plugin_registry = PluginRegistry()
    return _global_plugin_registry
