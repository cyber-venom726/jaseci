"""Metrics plugin for performance tracking and analytics."""

import time
from typing import Any, Dict, Optional, List
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from jacagent.plugins.base import BasePlugin
from jacagent.plugins.hooks import hookimpl


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    requests_per_minute: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentMetrics:
    """Agent-specific metrics."""
    agent_id: str
    missions_completed: int = 0
    missions_failed: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    average_mission_time: float = 0.0
    success_rate: float = 0.0
    memory_operations: int = 0
    last_activity: datetime = field(default_factory=datetime.utcnow)


class MetricsPlugin(BasePlugin):
    """Plugin for collecting and analyzing performance metrics."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.window_size = self.config.get("window_size", 100)  # Rolling window size
        self.export_interval = self.config.get("export_interval", 300)  # Export every 5 minutes
        
        # Metrics storage
        self.global_metrics = PerformanceMetrics()
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.squad_metrics: Dict[str, Dict[str, Any]] = {}
        
        # Rolling windows for recent performance
        self.recent_execution_times: deque = deque(maxlen=self.window_size)
        self.recent_requests: deque = deque(maxlen=self.window_size)
        
        # Time-series data
        self.hourly_stats: Dict[str, List[float]] = defaultdict(list)
        
        # Start time for rate calculations
        self.start_time = datetime.utcnow()
    
    def get_name(self) -> str:
        return "metrics"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Performance tracking and analytics for agents and squads"
    
    def _update_global_metrics(self, execution_time: float, success: bool):
        """Update global performance metrics."""
        self.global_metrics.total_requests += 1
        if success:
            self.global_metrics.successful_requests += 1
        else:
            self.global_metrics.failed_requests += 1
        
        self.global_metrics.total_execution_time += execution_time
        self.global_metrics.average_execution_time = (
            self.global_metrics.total_execution_time / self.global_metrics.total_requests
        )
        
        self.global_metrics.min_execution_time = min(
            self.global_metrics.min_execution_time, execution_time
        )
        self.global_metrics.max_execution_time = max(
            self.global_metrics.max_execution_time, execution_time
        )
        
        # Update rolling windows
        self.recent_execution_times.append(execution_time)
        self.recent_requests.append(datetime.utcnow())
        
        # Calculate requests per minute
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        recent_count = sum(1 for req_time in self.recent_requests if req_time > minute_ago)
        self.global_metrics.requests_per_minute = recent_count
        
        self.global_metrics.last_updated = now
    
    def _get_or_create_agent_metrics(self, agent_id: str) -> AgentMetrics:
        """Get or create metrics for an agent."""
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id)
        return self.agent_metrics[agent_id]
    
    @hookimpl
    def agent_created(self, agent):
        """Track agent creation."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.last_activity = datetime.utcnow()
    
    @hookimpl
    def mission_started(self, mission, agent):
        """Track mission start."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.last_activity = datetime.utcnow()
        
        # Store mission start time for duration calculation
        if not hasattr(mission, '_start_time'):
            mission._start_time = time.time()
    
    @hookimpl
    def mission_completed(self, mission, agent, result):
        """Track mission completion."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        
        # Calculate execution time
        execution_time = time.time() - getattr(mission, '_start_time', time.time())
        
        if result.success:
            metrics.missions_completed += 1
        else:
            metrics.missions_failed += 1
        
        # Update success rate
        total_missions = metrics.missions_completed + metrics.missions_failed
        metrics.success_rate = metrics.missions_completed / total_missions if total_missions > 0 else 0.0
        
        # Update average mission time
        if metrics.missions_completed > 0:
            metrics.average_mission_time = (
                (metrics.average_mission_time * (metrics.missions_completed - 1) + execution_time) 
                / metrics.missions_completed
            )
        
        metrics.last_activity = datetime.utcnow()
        
        # Update global metrics
        self._update_global_metrics(execution_time, result.success)
    
    @hookimpl
    def llm_request_started(self, agent, prompt, context):
        """Track LLM request start."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.total_llm_calls += 1
        metrics.last_activity = datetime.utcnow()
    
    @hookimpl
    def llm_response_received(self, agent, prompt, response, metrics_data):
        """Track LLM response."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.last_activity = datetime.utcnow()
        
        # Track token usage if available
        if isinstance(metrics_data, dict) and 'tokens_used' in metrics_data:
            hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
            self.hourly_stats[f"tokens_{hour_key}"].append(metrics_data['tokens_used'])
    
    @hookimpl
    def tool_execution_started(self, agent, tool_name, parameters):
        """Track tool execution start."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.total_tool_calls += 1
        metrics.last_activity = datetime.utcnow()
    
    @hookimpl
    def tool_execution_completed(self, agent, tool_name, result, execution_time):
        """Track tool execution completion."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.last_activity = datetime.utcnow()
        
        # Track tool performance
        hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
        self.hourly_stats[f"tool_{tool_name}_{hour_key}"].append(execution_time)
    
    @hookimpl
    def memory_stored(self, agent, memory_type, content):
        """Track memory operations."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.memory_operations += 1
        metrics.last_activity = datetime.utcnow()
    
    @hookimpl
    def memory_retrieved(self, agent, memory_type, query, results):
        """Track memory retrieval."""
        metrics = self._get_or_create_agent_metrics(agent.id)
        metrics.memory_operations += 1
        metrics.last_activity = datetime.utcnow()
    
    @hookimpl
    def squad_execution_started(self, squad):
        """Track squad execution start."""
        self.squad_metrics[squad.id] = {
            "start_time": datetime.utcnow(),
            "agent_count": len(squad.agents),
            "mission_count": len(squad.missions),
            "execution_pattern": squad.config.execution_pattern.value
        }
    
    @hookimpl
    def squad_execution_completed(self, squad, result):
        """Track squad execution completion."""
        if squad.id in self.squad_metrics:
            start_time = self.squad_metrics[squad.id]["start_time"]
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.squad_metrics[squad.id].update({
                "end_time": datetime.utcnow(),
                "execution_time": execution_time,
                "success": result.success,
                "successful_missions": sum(1 for r in result.results if r.success),
                "failed_missions": sum(1 for r in result.results if not r.success)
            })
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global performance metrics."""
        return {
            "total_requests": self.global_metrics.total_requests,
            "successful_requests": self.global_metrics.successful_requests,
            "failed_requests": self.global_metrics.failed_requests,
            "success_rate": (
                self.global_metrics.successful_requests / self.global_metrics.total_requests
                if self.global_metrics.total_requests > 0 else 0.0
            ),
            "average_execution_time": self.global_metrics.average_execution_time,
            "min_execution_time": (
                self.global_metrics.min_execution_time 
                if self.global_metrics.min_execution_time != float('inf') else 0.0
            ),
            "max_execution_time": self.global_metrics.max_execution_time,
            "requests_per_minute": self.global_metrics.requests_per_minute,
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "last_updated": self.global_metrics.last_updated.isoformat()
        }
    
    def get_agent_metrics(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for specific agent or all agents."""
        if agent_id:
            if agent_id in self.agent_metrics:
                metrics = self.agent_metrics[agent_id]
                return {
                    "agent_id": metrics.agent_id,
                    "missions_completed": metrics.missions_completed,
                    "missions_failed": metrics.missions_failed,
                    "success_rate": metrics.success_rate,
                    "total_llm_calls": metrics.total_llm_calls,
                    "total_tool_calls": metrics.total_tool_calls,
                    "average_mission_time": metrics.average_mission_time,
                    "memory_operations": metrics.memory_operations,
                    "last_activity": metrics.last_activity.isoformat()
                }
            return {}
        
        # Return all agent metrics
        return {
            agent_id: {
                "agent_id": metrics.agent_id,
                "missions_completed": metrics.missions_completed,
                "missions_failed": metrics.missions_failed,
                "success_rate": metrics.success_rate,
                "total_llm_calls": metrics.total_llm_calls,
                "total_tool_calls": metrics.total_tool_calls,
                "average_mission_time": metrics.average_mission_time,
                "memory_operations": metrics.memory_operations,
                "last_activity": metrics.last_activity.isoformat()
            }
            for agent_id, metrics in self.agent_metrics.items()
        }
    
    def get_squad_metrics(self, squad_id: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for specific squad or all squads."""
        if squad_id:
            return self.squad_metrics.get(squad_id, {})
        return self.squad_metrics.copy()
    
    def get_recent_performance(self) -> Dict[str, Any]:
        """Get recent performance metrics."""
        if not self.recent_execution_times:
            return {}
        
        recent_times = list(self.recent_execution_times)
        return {
            "recent_average": sum(recent_times) / len(recent_times),
            "recent_min": min(recent_times),
            "recent_max": max(recent_times),
            "sample_size": len(recent_times)
        }
    
    def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics for external monitoring."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "global_metrics": self.get_global_metrics(),
            "agent_metrics": self.get_agent_metrics(),
            "squad_metrics": self.get_squad_metrics(),
            "recent_performance": self.get_recent_performance(),
            "hourly_stats": dict(self.hourly_stats)
        }
