"""Logging plugin for comprehensive activity tracking."""

import time
import json
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path

from jacagent.plugins.base import BasePlugin
from jacagent.plugins.hooks import hookimpl


class LoggingPlugin(BasePlugin):
    """Plugin for comprehensive logging of agent activities."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.log_file = self.config.get("log_file", "jacagent.log")
        self.log_level = self.config.get("log_level", "INFO")
        self.include_context = self.config.get("include_context", True)
        
        # Ensure log directory exists
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_name(self) -> str:
        return "logging"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Comprehensive logging for agent activities and LLM interactions"
    
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event to file."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Failed to write log entry: {e}")
    
    @hookimpl
    def agent_created(self, agent):
        """Log when an agent is created."""
        self._log_event("agent_created", {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "role": agent.role,
            "capabilities": getattr(agent.config, 'capabilities', [])
        })
    
    @hookimpl
    def mission_started(self, mission, agent):
        """Log when a mission starts."""
        self._log_event("mission_started", {
            "mission_id": mission.id,
            "agent_id": agent.id,
            "objective": mission.objective,
            "mission_type": mission.mission_type.value
        })
    
    @hookimpl
    def mission_completed(self, mission, agent, result):
        """Log when a mission completes."""
        self._log_event("mission_completed", {
            "mission_id": mission.id,
            "agent_id": agent.id,
            "success": result.success,
            "execution_time": getattr(result, 'execution_time', 0),
            "steps_completed": len(getattr(result, 'step_results', []))
        })
    
    @hookimpl
    def llm_request_started(self, agent, prompt, context):
        """Log when an LLM request starts."""
        log_data = {
            "agent_id": agent.id,
            "prompt_length": len(prompt),
            "has_context": bool(context)
        }
        
        if self.include_context and context:
            log_data["context"] = context
        
        self._log_event("llm_request_started", log_data)
    
    @hookimpl
    def llm_response_received(self, agent, prompt, response, metrics):
        """Log when an LLM response is received."""
        self._log_event("llm_response_received", {
            "agent_id": agent.id,
            "response_length": len(response) if response else 0,
            "tokens_used": metrics.get("tokens_used", 0),
            "response_time": metrics.get("response_time", 0)
        })
    
    @hookimpl
    def tool_execution_started(self, agent, tool_name, parameters):
        """Log when tool execution starts."""
        self._log_event("tool_execution_started", {
            "agent_id": agent.id,
            "tool_name": tool_name,
            "parameter_count": len(parameters) if parameters else 0
        })
    
    @hookimpl
    def tool_execution_completed(self, agent, tool_name, result, execution_time):
        """Log when tool execution completes."""
        self._log_event("tool_execution_completed", {
            "agent_id": agent.id,
            "tool_name": tool_name,
            "success": result.get("success", False) if isinstance(result, dict) else bool(result),
            "execution_time": execution_time
        })
    
    @hookimpl
    def memory_stored(self, agent, memory_type, content):
        """Log when memory is stored."""
        self._log_event("memory_stored", {
            "agent_id": agent.id,
            "memory_type": memory_type,
            "content_length": len(str(content))
        })
    
    @hookimpl
    def memory_retrieved(self, agent, memory_type, query, results):
        """Log when memory is retrieved."""
        self._log_event("memory_retrieved", {
            "agent_id": agent.id,
            "memory_type": memory_type,
            "query": query,
            "results_count": len(results) if results else 0
        })
    
    @hookimpl
    def squad_execution_started(self, squad):
        """Log when squad execution starts."""
        self._log_event("squad_execution_started", {
            "squad_id": squad.id,
            "squad_name": squad.name,
            "agent_count": len(squad.agents),
            "mission_count": len(squad.missions),
            "execution_pattern": squad.config.execution_pattern.value
        })
    
    @hookimpl
    def squad_execution_completed(self, squad, result):
        """Log when squad execution completes."""
        self._log_event("squad_execution_completed", {
            "squad_id": squad.id,
            "success": result.success,
            "total_missions": len(result.results),
            "successful_missions": sum(1 for r in result.results if r.success),
            "execution_time": result.execution_time
        })
    
    @hookimpl
    def error_occurred(self, error, context):
        """Log when an error occurs."""
        self._log_event("error_occurred", {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context
        })
