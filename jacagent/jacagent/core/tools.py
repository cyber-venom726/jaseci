"""Tool system for JacAgent framework."""

import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

from jacagent.exceptions import ToolError
from jacagent.plugins.hooks import get_hook_manager


class ToolType(str, Enum):
    """Types of tools."""
    FUNCTION = "function"
    API = "api"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    WEB_SCRAPER = "web_scraper"
    CALCULATOR = "calculator"
    CUSTOM = "custom"


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class ToolMetadata(BaseModel):
    """Metadata for a tool."""
    name: str
    description: str
    tool_type: ToolType
    parameters: List[ToolParameter]
    return_type: str
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    author: Optional[str] = None


class ToolResult(BaseModel):
    """Result from tool execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time: float = 0.0


class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._hook_manager = get_hook_manager()
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Tool metadata."""
        pass
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> ToolResult:
        """Execute the tool."""
        pass
    
    async def execute_with_hooks(
        self, 
        *args, 
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ToolResult:
        """Execute tool with hook integration."""
        import time
        
        context = context or {}
        start_time = time.time()
        
        # Before hook
        hook_results = await self._hook_manager.call_hook(
            "before_tool_execute",
            tool=self,
            args=args,
            kwargs=kwargs,
            context=context
        )
        
        # Apply hook transformations
        for result in hook_results:
            if isinstance(result, tuple) and len(result) == 2:
                args, kwargs = result
        
        try:
            # Execute tool
            result = await self.execute(*args, **kwargs)
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            # After hook
            hook_results = await self._hook_manager.call_hook(
                "after_tool_execute",
                tool=self,
                result=result,
                context=context
            )
            
            # Apply hook transformations
            for hook_result in hook_results:
                if isinstance(hook_result, ToolResult):
                    result = hook_result
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def validate_parameters(self, *args, **kwargs) -> None:
        """Validate tool parameters."""
        # Basic validation - override in subclasses for more sophisticated validation
        required_params = [p.name for p in self.metadata.parameters if p.required]
        provided_params = set(kwargs.keys())
        
        missing_params = set(required_params) - provided_params
        if missing_params:
            raise ToolError(f"Missing required parameters: {missing_params}")


class FunctionTool(BaseTool):
    """Tool that wraps a function."""
    
    def __init__(self, func: Callable, metadata: ToolMetadata, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.func = func
        self._metadata = metadata
    
    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata
    
    async def execute(self, *args, **kwargs) -> ToolResult:
        """Execute the wrapped function."""
        try:
            self.validate_parameters(*args, **kwargs)
            
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(*args, **kwargs)
            else:
                result = self.func(*args, **kwargs)
            
            return ToolResult(success=True, result=result)
            
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CalculatorTool(BaseTool):
    """Simple calculator tool."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calculator",
            description="Perform mathematical calculations",
            tool_type=ToolType.CALCULATOR,
            parameters=[
                ToolParameter(
                    name="expression",
                    type="str",
                    description="Mathematical expression to evaluate",
                    required=True
                )
            ],
            return_type="float",
            examples=[
                {"expression": "2 + 2", "result": 4},
                {"expression": "3.14 * 2", "result": 6.28}
            ],
            tags=["math", "calculation"]
        )
    
    async def execute(self, expression: str) -> ToolResult:
        """Execute mathematical calculation."""
        try:
            # Basic safety check - only allow certain characters
            allowed_chars = set("0123456789+-*/().,e ")
            if not all(c in allowed_chars for c in expression):
                raise ValueError("Invalid characters in expression")
            
            result = eval(expression)
            return ToolResult(success=True, result=result)
            
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebScraperTool(BaseTool):
    """Web scraping tool."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="web_scraper",
            description="Scrape content from web pages",
            tool_type=ToolType.WEB_SCRAPER,
            parameters=[
                ToolParameter(
                    name="url",
                    type="str",
                    description="URL to scrape",
                    required=True
                ),
                ToolParameter(
                    name="selector",
                    type="str",
                    description="CSS selector for content extraction",
                    required=False
                )
            ],
            return_type="str",
            tags=["web", "scraping", "content"]
        )
    
    async def execute(self, url: str, selector: Optional[str] = None) -> ToolResult:
        """Scrape web content."""
        try:
            import httpx
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                if selector:
                    elements = soup.select(selector)
                    content = "\n".join([elem.get_text().strip() for elem in elements])
                else:
                    content = soup.get_text().strip()
                
                return ToolResult(
                    success=True, 
                    result=content,
                    metadata={"url": url, "status_code": response.status_code}
                )
                
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileSystemTool(BaseTool):
    """File system operations tool."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="file_system",
            description="Perform file system operations",
            tool_type=ToolType.FILE_SYSTEM,
            parameters=[
                ToolParameter(
                    name="operation",
                    type="str",
                    description="Operation to perform",
                    required=True,
                    enum=["read", "write", "list", "exists", "delete"]
                ),
                ToolParameter(
                    name="path",
                    type="str",
                    description="File or directory path",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type="str",
                    description="Content to write (for write operation)",
                    required=False
                )
            ],
            return_type="Any",
            tags=["file", "system", "io"]
        )
    
    async def execute(self, operation: str, path: str, content: Optional[str] = None) -> ToolResult:
        """Execute file system operation."""
        try:
            import aiofiles
            import os
            from pathlib import Path
            
            path_obj = Path(path)
            
            if operation == "read":
                if not path_obj.exists():
                    raise FileNotFoundError(f"File not found: {path}")
                
                async with aiofiles.open(path, 'r') as f:
                    content = await f.read()
                return ToolResult(success=True, result=content)
            
            elif operation == "write":
                if content is None:
                    raise ValueError("Content required for write operation")
                
                # Create parent directories if they don't exist
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(path, 'w') as f:
                    await f.write(content)
                return ToolResult(success=True, result=f"Written to {path}")
            
            elif operation == "list":
                if not path_obj.exists():
                    raise FileNotFoundError(f"Directory not found: {path}")
                
                if path_obj.is_file():
                    result = [path_obj.name]
                else:
                    result = [item.name for item in path_obj.iterdir()]
                
                return ToolResult(success=True, result=result)
            
            elif operation == "exists":
                return ToolResult(success=True, result=path_obj.exists())
            
            elif operation == "delete":
                if path_obj.exists():
                    if path_obj.is_file():
                        path_obj.unlink()
                    else:
                        import shutil
                        shutil.rmtree(path)
                    return ToolResult(success=True, result=f"Deleted {path}")
                else:
                    return ToolResult(success=True, result=f"Path does not exist: {path}")
            
            else:
                raise ValueError(f"Unsupported operation: {operation}")
                
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, type] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register built-in tools."""
        builtin_tools = [
            CalculatorTool,
            WebScraperTool,
            FileSystemTool,
        ]
        
        for tool_class in builtin_tools:
            temp_instance = tool_class()
            self._tool_classes[temp_instance.metadata.name] = tool_class
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.metadata.name] = tool
    
    def register_tool_class(self, tool_class: type) -> None:
        """Register a tool class."""
        if not issubclass(tool_class, BaseTool):
            raise ToolError("Tool class must inherit from BaseTool")
        
        temp_instance = tool_class()
        self._tool_classes[temp_instance.metadata.name] = tool_class
    
    def create_tool(self, tool_name: str, config: Optional[Dict[str, Any]] = None) -> BaseTool:
        """Create a tool instance."""
        if tool_name in self._tools:
            return self._tools[tool_name]
        
        if tool_name in self._tool_classes:
            tool_class = self._tool_classes[tool_name]
            tool = tool_class(config)
            self._tools[tool_name] = tool
            return tool
        
        raise ToolError(f"Unknown tool: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool instance."""
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """List available tool names."""
        return list(set(self._tools.keys()) | set(self._tool_classes.keys()))
    
    def get_tool_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """Get tool metadata."""
        tool = self.get_tool(tool_name)
        if tool:
            return tool.metadata
        
        if tool_name in self._tool_classes:
            temp_instance = self._tool_classes[tool_name]()
            return temp_instance.metadata
        
        return None
    
    def search_tools(self, query: str, tags: Optional[List[str]] = None) -> List[str]:
        """Search for tools by query and tags."""
        results = []
        
        for tool_name in self.list_tools():
            metadata = self.get_tool_metadata(tool_name)
            if not metadata:
                continue
            
            # Check query match
            if query.lower() in metadata.name.lower() or query.lower() in metadata.description.lower():
                if not tags or any(tag in metadata.tags for tag in tags):
                    results.append(tool_name)
        
        return results
    
    def register_function_tool(
        self, 
        func: Callable, 
        name: str, 
        description: str,
        parameters: Optional[List[ToolParameter]] = None
    ) -> None:
        """Register a function as a tool."""
        if not parameters:
            # Auto-generate parameters from function signature
            sig = inspect.signature(func)
            parameters = []
            
            for param_name, param in sig.parameters.items():
                param_type = "str"  # Default type
                if param.annotation != param.empty:
                    param_type = param.annotation.__name__
                
                tool_param = ToolParameter(
                    name=param_name,
                    type=param_type,
                    description=f"Parameter {param_name}",
                    required=param.default == param.empty
                )
                parameters.append(tool_param)
        
        metadata = ToolMetadata(
            name=name,
            description=description,
            tool_type=ToolType.FUNCTION,
            parameters=parameters,
            return_type="Any"
        )
        
        tool = FunctionTool(func, metadata)
        self.register_tool(tool)


# Global tool registry instance
_global_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _global_tool_registry
    if _global_tool_registry is None:
        _global_tool_registry = ToolRegistry()
    return _global_tool_registry


# Decorator for registering functions as tools
def tool(name: str, description: str, parameters: Optional[List[ToolParameter]] = None):
    """Decorator to register a function as a tool."""
    def decorator(func):
        registry = get_tool_registry()
        registry.register_function_tool(func, name, description, parameters)
        return func
    return decorator
