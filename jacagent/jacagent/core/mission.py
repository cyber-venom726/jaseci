"""Mission system for JacAgent framework."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Union, Callable
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timedelta

from jacagent.exceptions import MissionError
from jacagent.plugins.hooks import get_hook_manager


class MissionStatus(str, Enum):
    """Mission execution status."""
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionPriority(int, Enum):
    """Mission priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class MissionType(str, Enum):
    """Types of missions."""
    SIMPLE = "simple"
    COMPLEX = "complex"
    COLLABORATIVE = "collaborative"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class MissionConstraint(BaseModel):
    """Constraint for mission execution."""
    name: str
    value: Any
    description: str
    enforced: bool = True


class MissionSuccessCriteria(BaseModel):
    """Success criteria for mission completion."""
    name: str
    description: str
    threshold: Optional[float] = None
    required: bool = True
    validator: Optional[str] = None  # Function name or expression


class MissionStep(BaseModel):
    """Individual step in a mission."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    estimated_time: Optional[int] = None  # seconds
    status: MissionStatus = MissionStatus.CREATED
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MissionResult(BaseModel):
    """Result of mission execution."""
    mission_id: str
    status: MissionStatus
    success: bool
    result: Any = None
    error: Optional[str] = None
    outputs: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0
    
    # Performance metrics
    efficiency_score: float = 0.0
    quality_score: float = 0.0
    creativity_score: float = 0.0


class Mission(BaseModel):
    """Enhanced mission with complex workflow support."""
    
    # Core Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Mission name")
    objective: str = Field(description="Clear mission objective")
    description: str = Field(default="", description="Detailed mission description")
    
    # Classification
    mission_type: MissionType = Field(default=MissionType.SIMPLE)
    priority: MissionPriority = Field(default=MissionPriority.NORMAL)
    
    # Requirements & Constraints
    success_criteria: List[MissionSuccessCriteria] = Field(default_factory=list)
    constraints: List[MissionConstraint] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    
    # Workflow
    steps: List[MissionStep] = Field(default_factory=list)
    current_step: Optional[str] = None
    
    # Execution Control
    max_attempts: int = Field(default=3, gt=0)
    timeout: int = Field(default=600, gt=0)  # seconds
    deadline: Optional[datetime] = None
    
    # Output Configuration
    output_format: str = Field(default="text")
    output_schema: Optional[Dict[str, Any]] = None
    output_validation: Optional[str] = None
    
    # State Management
    status: MissionStatus = Field(default=MissionStatus.CREATED)
    assigned_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Context & Dependencies
    context: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    dependent_missions: List[str] = Field(default_factory=list)
    
    # Results & Tracking
    result: Optional[MissionResult] = None
    attempts: int = 0
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Internal components
    _hook_manager = None
    _callbacks: List[Callable] = []
    
    class Config:
        arbitrary_types_allowed = True
        exclude = {"_hook_manager", "_callbacks"}
    
    def __init__(self, **data):
        super().__init__(**data)
        self._hook_manager = get_hook_manager()
        
        # Auto-generate steps for simple missions
        if self.mission_type == MissionType.SIMPLE and not self.steps:
            self._generate_simple_steps()
    
    def _generate_simple_steps(self):
        """Generate default steps for simple missions."""
        self.steps = [
            MissionStep(
                name="analyze_objective",
                description="Analyze the mission objective and plan approach"
            ),
            MissionStep(
                name="execute_mission",
                description="Execute the main mission objective"
            ),
            MissionStep(
                name="validate_result",
                description="Validate the result against success criteria"
            )
        ]
    
    def add_step(
        self, 
        name: str, 
        description: str,
        dependencies: Optional[List[str]] = None,
        required_capabilities: Optional[List[str]] = None,
        estimated_time: Optional[int] = None
    ) -> str:
        """Add a step to the mission."""
        step = MissionStep(
            name=name,
            description=description,
            dependencies=dependencies or [],
            required_capabilities=required_capabilities or [],
            estimated_time=estimated_time
        )
        self.steps.append(step)
        return step.id
    
    def add_success_criteria(
        self, 
        name: str, 
        description: str,
        threshold: Optional[float] = None,
        required: bool = True,
        validator: Optional[str] = None
    ) -> None:
        """Add success criteria to the mission."""
        criteria = MissionSuccessCriteria(
            name=name,
            description=description,
            threshold=threshold,
            required=required,
            validator=validator
        )
        self.success_criteria.append(criteria)
    
    def add_constraint(
        self, 
        name: str, 
        value: Any, 
        description: str,
        enforced: bool = True
    ) -> None:
        """Add a constraint to the mission."""
        constraint = MissionConstraint(
            name=name,
            value=value,
            description=description,
            enforced=enforced
        )
        self.constraints.append(constraint)
    
    def set_deadline(self, deadline: datetime) -> None:
        """Set mission deadline."""
        self.deadline = deadline
    
    def set_timeout(self, timeout: int) -> None:
        """Set mission timeout in seconds."""
        self.timeout = timeout
    
    def add_context(self, key: str, value: Any) -> None:
        """Add context information."""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context information."""
        return self.context.get(key, default)
    
    def add_dependency(self, mission_id: str) -> None:
        """Add a mission dependency."""
        if mission_id not in self.dependencies:
            self.dependencies.append(mission_id)
    
    def is_ready_to_start(self) -> bool:
        """Check if mission is ready to start."""
        return (
            self.status == MissionStatus.CREATED and
            self.assigned_agent is not None and
            len(self.dependencies) == 0  # Simplified - should check if dependencies are completed
        )
    
    def is_overdue(self) -> bool:
        """Check if mission is overdue."""
        if not self.deadline:
            return False
        return datetime.now() > self.deadline
    
    def is_timeout(self) -> bool:
        """Check if mission has timed out."""
        if not self.started_at:
            return False
        elapsed = (datetime.now() - self.started_at).total_seconds()
        return elapsed > self.timeout
    
    def get_next_step(self) -> Optional[MissionStep]:
        """Get the next step to execute."""
        for step in self.steps:
            if step.status == MissionStatus.CREATED:
                # Check if dependencies are satisfied
                if self._are_step_dependencies_satisfied(step):
                    return step
        return None
    
    def _are_step_dependencies_satisfied(self, step: MissionStep) -> bool:
        """Check if step dependencies are satisfied."""
        if not step.dependencies:
            return True
        
        for dep_id in step.dependencies:
            dep_step = self.get_step_by_id(dep_id)
            if not dep_step or dep_step.status != MissionStatus.COMPLETED:
                return False
        
        return True
    
    def get_step_by_id(self, step_id: str) -> Optional[MissionStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_step_by_name(self, step_name: str) -> Optional[MissionStep]:
        """Get step by name."""
        for step in self.steps:
            if step.name == step_name:
                return step
        return None
    
    def start_step(self, step_id: str) -> None:
        """Start a mission step."""
        step = self.get_step_by_id(step_id)
        if step:
            step.status = MissionStatus.IN_PROGRESS
            step.started_at = datetime.now()
            self.current_step = step_id
    
    def complete_step(self, step_id: str, result: Any = None) -> None:
        """Complete a mission step."""
        step = self.get_step_by_id(step_id)
        if step:
            step.status = MissionStatus.COMPLETED
            step.completed_at = datetime.now()
            step.result = result
            
            # Move to next step if available
            next_step = self.get_next_step()
            if next_step:
                self.current_step = next_step.id
            else:
                self.current_step = None
    
    def fail_step(self, step_id: str, error: str) -> None:
        """Fail a mission step."""
        step = self.get_step_by_id(step_id)
        if step:
            step.status = MissionStatus.FAILED
            step.completed_at = datetime.now()
            step.error = error
    
    def start(self, agent_id: str) -> None:
        """Start mission execution."""
        if self.status != MissionStatus.CREATED:
            raise MissionError(f"Mission {self.id} is not in CREATED status")
        
        self.status = MissionStatus.IN_PROGRESS
        self.assigned_agent = agent_id
        self.started_at = datetime.now()
        self.attempts += 1
        
        # Start first step
        first_step = self.get_next_step()
        if first_step:
            self.start_step(first_step.id)
    
    def complete(self, result: Any = None, outputs: Optional[Dict[str, Any]] = None) -> None:
        """Complete the mission."""
        self.status = MissionStatus.COMPLETED
        self.completed_at = datetime.now()
        
        execution_time = 0.0
        if self.started_at:
            execution_time = (self.completed_at - self.started_at).total_seconds()
        
        self.result = MissionResult(
            mission_id=self.id,
            status=self.status,
            success=True,
            result=result,
            outputs=outputs or {},
            execution_time=execution_time,
            steps_completed=len([s for s in self.steps if s.status == MissionStatus.COMPLETED]),
            steps_total=len(self.steps)
        )
    
    def fail(self, error: str) -> None:
        """Fail the mission."""
        self.status = MissionStatus.FAILED
        self.completed_at = datetime.now()
        
        execution_time = 0.0
        if self.started_at:
            execution_time = (self.completed_at - self.started_at).total_seconds()
        
        self.result = MissionResult(
            mission_id=self.id,
            status=self.status,
            success=False,
            error=error,
            execution_time=execution_time,
            steps_completed=len([s for s in self.steps if s.status == MissionStatus.COMPLETED]),
            steps_total=len(self.steps)
        )
    
    def cancel(self) -> None:
        """Cancel the mission."""
        self.status = MissionStatus.CANCELLED
        self.completed_at = datetime.now()
    
    def can_retry(self) -> bool:
        """Check if mission can be retried."""
        return (
            self.status == MissionStatus.FAILED and
            self.attempts < self.max_attempts
        )
    
    def retry(self) -> None:
        """Retry the mission."""
        if not self.can_retry():
            raise MissionError("Mission cannot be retried")
        
        # Reset mission state
        self.status = MissionStatus.CREATED
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.current_step = None
        
        # Reset step states
        for step in self.steps:
            step.status = MissionStatus.CREATED
            step.started_at = None
            step.completed_at = None
            step.result = None
            step.error = None
    
    def get_progress(self) -> Dict[str, Any]:
        """Get mission progress information."""
        total_steps = len(self.steps)
        completed_steps = len([s for s in self.steps if s.status == MissionStatus.COMPLETED])
        
        progress_percentage = 0.0
        if total_steps > 0:
            progress_percentage = (completed_steps / total_steps) * 100
        
        return {
            "mission_id": self.id,
            "status": self.status,
            "progress_percentage": progress_percentage,
            "steps_completed": completed_steps,
            "steps_total": total_steps,
            "current_step": self.current_step,
            "attempts": self.attempts,
            "execution_time": self._get_execution_time(),
            "is_overdue": self.is_overdue(),
            "is_timeout": self.is_timeout()
        }
    
    def _get_execution_time(self) -> float:
        """Get current execution time."""
        if not self.started_at:
            return 0.0
        
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    def log_event(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Log an event during mission execution."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "message": message,
            "data": data or {}
        }
        self.logs.append(log_entry)
    
    def add_callback(self, callback: Callable) -> None:
        """Add a callback function."""
        self._callbacks.append(callback)
    
    async def notify_callbacks(self, event: str, data: Dict[str, Any]) -> None:
        """Notify all callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, data)
                else:
                    callback(event, data)
            except Exception as e:
                self.log_event("callback_error", f"Callback failed: {e}")
    
    # Factory methods for common mission types
    @classmethod
    def simple(
        cls,
        objective: str,
        name: Optional[str] = None,
        **kwargs
    ) -> "Mission":
        """Create a simple mission."""
        return cls(
            name=name or f"Simple_{objective[:20]}",
            objective=objective,
            mission_type=MissionType.SIMPLE,
            **kwargs
        )
    
    @classmethod
    def collaborative(
        cls,
        objective: str,
        workflow: List[str],
        name: Optional[str] = None,
        **kwargs
    ) -> "Mission":
        """Create a collaborative mission."""
        mission = cls(
            name=name or f"Collaborative_{objective[:20]}",
            objective=objective,
            mission_type=MissionType.COLLABORATIVE,
            **kwargs
        )
        
        # Add steps from workflow
        for i, step_name in enumerate(workflow):
            dependencies = [mission.steps[i-1].id] if i > 0 else []
            mission.add_step(
                name=step_name,
                description=f"Execute {step_name} phase",
                dependencies=dependencies
            )
        
        return mission
    
    @classmethod
    def complex(
        cls,
        objective: str,
        steps: List[Dict[str, Any]],
        name: Optional[str] = None,
        **kwargs
    ) -> "Mission":
        """Create a complex mission with custom steps."""
        mission = cls(
            name=name or f"Complex_{objective[:20]}",
            objective=objective,
            mission_type=MissionType.COMPLEX,
            **kwargs
        )
        
        # Add custom steps
        for step_data in steps:
            mission.add_step(**step_data)
        
        return mission
