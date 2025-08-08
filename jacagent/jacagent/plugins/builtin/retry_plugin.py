"""Retry plugin for automatic failure recovery."""

import time
import asyncio
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from jacagent.plugins.base import BasePlugin
from jacagent.plugins.hooks import hookimpl
from jacagent.exceptions import JacAgentError


class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CUSTOM = "custom"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_on_exceptions: List[type] = field(default_factory=list)
    custom_strategy: Optional[Callable[[int], float]] = None


@dataclass
class RetryAttempt:
    """Record of a retry attempt."""
    attempt_number: int
    timestamp: datetime
    error: Optional[Exception] = None
    delay_before_next: float = 0.0


class RetryPlugin(BasePlugin):
    """Plugin for automatic retry mechanisms with various strategies."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        
        # Default retry configurations for different operations
        self.llm_retry_config = RetryConfig(
            max_attempts=self.config.get("llm_max_attempts", 3),
            strategy=RetryStrategy(self.config.get("llm_strategy", "exponential")),
            base_delay=self.config.get("llm_base_delay", 1.0),
            max_delay=self.config.get("llm_max_delay", 30.0)
        )
        
        self.tool_retry_config = RetryConfig(
            max_attempts=self.config.get("tool_max_attempts", 2),
            strategy=RetryStrategy(self.config.get("tool_strategy", "fixed")),
            base_delay=self.config.get("tool_base_delay", 0.5),
            max_delay=self.config.get("tool_max_delay", 10.0)
        )
        
        self.mission_retry_config = RetryConfig(
            max_attempts=self.config.get("mission_max_attempts", 2),
            strategy=RetryStrategy(self.config.get("mission_strategy", "linear")),
            base_delay=self.config.get("mission_base_delay", 2.0),
            max_delay=self.config.get("mission_max_delay", 60.0)
        )
        
        # Track retry attempts
        self.retry_history: Dict[str, List[RetryAttempt]] = {}
        
        # Circuit breaker functionality
        self.failure_counts: Dict[str, int] = {}
        self.circuit_breaker_threshold = self.config.get("circuit_breaker_threshold", 5)
        self.circuit_breaker_timeout = self.config.get("circuit_breaker_timeout", 300)  # 5 minutes
        self.circuit_breaker_state: Dict[str, datetime] = {}
    
    def get_name(self) -> str:
        return "retry"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Automatic retry mechanisms with circuit breaker functionality"
    
    def _calculate_delay(self, config: RetryConfig, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_factor ** (attempt - 1))
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt
        elif config.strategy == RetryStrategy.CUSTOM and config.custom_strategy:
            delay = config.custom_strategy(attempt)
        else:
            delay = config.base_delay
        
        # Apply max delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter:
            import random
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def _should_retry(self, config: RetryConfig, error: Exception, attempt: int) -> bool:
        """Determine if operation should be retried."""
        if attempt >= config.max_attempts:
            return False
        
        # Check if error type is in retry list (if specified)
        if config.retry_on_exceptions:
            return any(isinstance(error, exc_type) for exc_type in config.retry_on_exceptions)
        
        # Default retry logic for common error types
        retry_exceptions = (
            ConnectionError,
            TimeoutError,
            JacAgentError
        )
        
        return isinstance(error, retry_exceptions)
    
    def _is_circuit_breaker_open(self, operation_key: str) -> bool:
        """Check if circuit breaker is open for operation."""
        if operation_key not in self.circuit_breaker_state:
            return False
        
        open_time = self.circuit_breaker_state[operation_key]
        timeout_time = open_time + timedelta(seconds=self.circuit_breaker_timeout)
        
        if datetime.utcnow() > timeout_time:
            # Circuit breaker timeout expired, reset
            del self.circuit_breaker_state[operation_key]
            self.failure_counts[operation_key] = 0
            return False
        
        return True
    
    def _record_failure(self, operation_key: str):
        """Record failure and potentially open circuit breaker."""
        self.failure_counts[operation_key] = self.failure_counts.get(operation_key, 0) + 1
        
        if self.failure_counts[operation_key] >= self.circuit_breaker_threshold:
            self.circuit_breaker_state[operation_key] = datetime.utcnow()
    
    def _record_success(self, operation_key: str):
        """Record success and reset failure count."""
        self.failure_counts[operation_key] = 0
        if operation_key in self.circuit_breaker_state:
            del self.circuit_breaker_state[operation_key]
    
    async def retry_operation(
        self,
        operation: Callable,
        config: RetryConfig,
        operation_key: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with retry logic."""
        # Check circuit breaker
        if self._is_circuit_breaker_open(operation_key):
            raise JacAgentError(f"Circuit breaker is open for operation: {operation_key}")
        
        attempts = []
        last_error = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                result = await operation(*args, **kwargs) if asyncio.iscoroutinefunction(operation) else operation(*args, **kwargs)
                
                # Record success
                self._record_success(operation_key)
                
                # Log successful attempt if there were previous failures
                if attempts:
                    attempts.append(RetryAttempt(
                        attempt_number=attempt,
                        timestamp=datetime.utcnow()
                    ))
                    self.retry_history[operation_key] = attempts
                
                return result
                
            except Exception as error:
                last_error = error
                
                # Record attempt
                delay = self._calculate_delay(config, attempt) if attempt < config.max_attempts else 0.0
                attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.utcnow(),
                    error=error,
                    delay_before_next=delay
                ))
                
                # Check if we should retry
                if not self._should_retry(config, error, attempt):
                    break
                
                if attempt < config.max_attempts:
                    # Wait before next attempt
                    if delay > 0:
                        await asyncio.sleep(delay)
        
        # All attempts failed
        self._record_failure(operation_key)
        self.retry_history[operation_key] = attempts
        
        raise JacAgentError(f"Operation failed after {len(attempts)} attempts: {last_error}")
    
    @hookimpl
    def modify_llm_request(self, agent, prompt, context):
        """Wrap LLM requests with retry logic."""
        original_call = agent.llm.generate
        
        async def retry_llm_call(*args, **kwargs):
            return await self.retry_operation(
                original_call,
                self.llm_retry_config,
                f"llm_{agent.id}",
                *args,
                **kwargs
            )
        
        # Temporarily replace the method
        agent.llm.generate = retry_llm_call
        return {"prompt": prompt, "context": context}
    
    @hookimpl
    def modify_tool_execution(self, agent, tool_name, parameters):
        """Wrap tool execution with retry logic."""
        # This would be implemented based on the tool execution framework
        return {"tool_name": tool_name, "parameters": parameters}
    
    @hookimpl
    def mission_failed(self, mission, agent, error):
        """Handle mission failure with retry logic."""
        operation_key = f"mission_{mission.id}"
        
        # Check if we should retry the mission
        if self._should_retry(self.mission_retry_config, error, 1):
            # Mark mission for retry
            if not hasattr(mission, '_retry_count'):
                mission._retry_count = 0
            
            mission._retry_count += 1
            
            if mission._retry_count < self.mission_retry_config.max_attempts:
                # Schedule retry
                delay = self._calculate_delay(self.mission_retry_config, mission._retry_count)
                
                # Record retry attempt
                if operation_key not in self.retry_history:
                    self.retry_history[operation_key] = []
                
                self.retry_history[operation_key].append(RetryAttempt(
                    attempt_number=mission._retry_count,
                    timestamp=datetime.utcnow(),
                    error=error,
                    delay_before_next=delay
                ))
                
                return {"should_retry": True, "delay": delay}
        
        # Record final failure
        self._record_failure(operation_key)
        return {"should_retry": False}
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get retry statistics."""
        stats = {
            "total_operations": len(self.retry_history),
            "operations_with_retries": sum(1 for attempts in self.retry_history.values() if len(attempts) > 1),
            "circuit_breakers_open": len(self.circuit_breaker_state),
            "operation_details": {}
        }
        
        for operation_key, attempts in self.retry_history.items():
            stats["operation_details"][operation_key] = {
                "total_attempts": len(attempts),
                "success": attempts[-1].error is None,
                "first_attempt": attempts[0].timestamp.isoformat(),
                "last_attempt": attempts[-1].timestamp.isoformat(),
                "total_delay": sum(attempt.delay_before_next for attempt in attempts)
            }
        
        return stats
    
    def reset_circuit_breaker(self, operation_key: str):
        """Manually reset circuit breaker for operation."""
        if operation_key in self.circuit_breaker_state:
            del self.circuit_breaker_state[operation_key]
        self.failure_counts[operation_key] = 0
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "open_circuits": list(self.circuit_breaker_state.keys()),
            "failure_counts": self.failure_counts.copy(),
            "threshold": self.circuit_breaker_threshold,
            "timeout_seconds": self.circuit_breaker_timeout
        }
