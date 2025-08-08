"""Custom exceptions for JacAgent framework."""

from typing import Any, Dict, Optional


class JacAgentError(Exception):
    """Base exception for all JacAgent errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(message)
    
    def __str__(self) -> str:
        base_msg = self.message
        if self.error_code:
            base_msg = f"[{self.error_code}] {base_msg}"
        if self.context:
            base_msg += f" (Context: {self.context})"
        return base_msg


class AgentError(JacAgentError):
    """Raised when agent-related operations fail."""
    pass


class MissionError(JacAgentError):
    """Raised when mission execution fails."""
    pass


class SquadError(JacAgentError):
    """Raised when squad operations fail."""
    pass


class LLMError(JacAgentError):
    """Raised when LLM operations fail."""
    pass


class MemoryError(JacAgentError):
    """Raised when memory operations fail."""
    pass


class ToolError(JacAgentError):
    """Raised when tool operations fail."""
    pass


class PluginError(JacAgentError):
    """Raised when plugin operations fail."""
    pass


class ConfigurationError(JacAgentError):
    """Raised when configuration is invalid."""
    pass


class ValidationError(JacAgentError):
    """Raised when validation fails."""
    pass


class SecurityError(JacAgentError):
    """Raised when security checks fail."""
    pass


class TimeoutError(JacAgentError):
    """Raised when operations timeout."""
    pass


class ResourceError(JacAgentError):
    """Raised when resource operations fail."""
    pass
