"""Squad orchestration system for JacAgent framework."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from jacagent.exceptions import SquadError
from jacagent.core.agent import Agent
from jacagent.core.mission import Mission, MissionStatus, MissionResult
from jacagent.plugins.hooks import get_hook_manager


class SquadStatus(str, Enum):
    """Squad execution status."""
    IDLE = "idle"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationPattern(str, Enum):
    """Orchestration patterns for squad execution."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"
    PIPELINE = "pipeline"
    CONSENSUS = "consensus"


class SquadMetrics(BaseModel):
    """Squad performance metrics."""
    missions_completed: int = 0
    missions_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    agent_utilization: Dict[str, float] = Field(default_factory=dict)
    collaboration_score: float = 0.0
    efficiency_score: float = 0.0
    success_rate: float = 0.0
    
    def update_success_rate(self):
        """Update success rate calculation."""
        total = self.missions_completed + self.missions_failed
        if total > 0:
            self.success_rate = self.missions_completed / total


class SquadConfig(BaseModel):
    """Configuration for squad behavior."""
    orchestration: OrchestrationPattern = OrchestrationPattern.ADAPTIVE
    max_concurrent_missions: int = Field(default=5, gt=0)
    mission_timeout: int = Field(default=1800, gt=0)  # 30 minutes default
    enable_collaboration: bool = Field(default=True)
    enable_memory_sharing: bool = Field(default=True)
    enable_learning: bool = Field(default=True)
    retry_failed_missions: bool = Field(default=True)
    auto_assign_agents: bool = Field(default=True)
    load_balancing: bool = Field(default=True)


class Squad(BaseModel):
    """Enhanced squad orchestrator with advanced collaboration patterns."""
    
    # Core Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Squad name")
    description: str = Field(default="", description="Squad description")
    
    # Configuration
    config: SquadConfig = Field(default_factory=SquadConfig)
    
    # Members and Missions
    agents: List[Agent] = Field(default_factory=list)
    missions: List[Mission] = Field(default_factory=list)
    
    # State Management
    status: SquadStatus = Field(default=SquadStatus.IDLE)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Execution Tracking
    current_missions: Dict[str, str] = Field(default_factory=dict)  # mission_id -> agent_id
    completed_missions: List[str] = Field(default_factory=list)
    failed_missions: List[str] = Field(default_factory=list)
    
    # Performance Metrics
    metrics: SquadMetrics = Field(default_factory=SquadMetrics)
    
    # Context and Memory
    shared_context: Dict[str, Any] = Field(default_factory=dict)
    shared_memory: Dict[str, Any] = Field(default_factory=dict)
    
    # Internal components
    _hook_manager = None
    _execution_lock = None
    
    class Config:
        arbitrary_types_allowed = True
        exclude = {"_hook_manager", "_execution_lock"}
    
    def __init__(self, **data):
        super().__init__(**data)
        self._hook_manager = get_hook_manager()
        self._execution_lock = asyncio.Lock()
    
    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the squad."""
        if agent not in self.agents:
            self.agents.append(agent)
            self.metrics.agent_utilization[agent.id] = 0.0
    
    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the squad."""
        for i, agent in enumerate(self.agents):
            if agent.id == agent_id:
                del self.agents[i]
                if agent_id in self.metrics.agent_utilization:
                    del self.metrics.agent_utilization[agent_id]
                return True
        return False
    
    def add_mission(self, mission: Mission) -> None:
        """Add a mission to the squad."""
        if mission not in self.missions:
            self.missions.append(mission)
    
    def remove_mission(self, mission_id: str) -> bool:
        """Remove a mission from the squad."""
        for i, mission in enumerate(self.missions):
            if mission.id == mission_id:
                del self.missions[i]
                return True
        return False
    
    def get_agent_by_id(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None
    
    def get_mission_by_id(self, mission_id: str) -> Optional[Mission]:
        """Get mission by ID."""
        for mission in self.missions:
            if mission.id == mission_id:
                return mission
        return None
    
    def get_available_agents(self) -> List[Agent]:
        """Get agents that are currently available."""
        busy_agents = set(self.current_missions.values())
        return [agent for agent in self.agents if agent.id not in busy_agents]
    
    def get_pending_missions(self) -> List[Mission]:
        """Get missions that are ready to be executed."""
        return [
            mission for mission in self.missions
            if mission.status == MissionStatus.CREATED and mission.is_ready_to_start()
        ]
    
    def assign_mission_to_agent(self, mission: Mission, agent: Agent) -> None:
        """Assign a mission to an agent."""
        if mission.id in self.current_missions:
            raise SquadError(f"Mission {mission.id} is already assigned")
        
        if agent.id in self.current_missions.values():
            raise SquadError(f"Agent {agent.id} is already busy")
        
        self.current_missions[mission.id] = agent.id
        mission.start(agent.id)
    
    def auto_assign_missions(self) -> List[tuple]:
        """Automatically assign missions to available agents."""
        available_agents = self.get_available_agents()
        pending_missions = self.get_pending_missions()
        
        assignments = []
        
        for mission in pending_missions:
            if not available_agents:
                break
            
            # Find best agent for mission
            best_agent = self._find_best_agent_for_mission(mission, available_agents)
            if best_agent:
                assignments.append((mission, best_agent))
                available_agents.remove(best_agent)
        
        return assignments
    
    def _find_best_agent_for_mission(self, mission: Mission, available_agents: List[Agent]) -> Optional[Agent]:
        """Find the best agent for a mission based on capabilities and load."""
        if not available_agents:
            return None
        
        # Score agents based on capability match and current load
        scored_agents = []
        
        for agent in available_agents:
            score = 0.0
            
            # Capability matching
            agent_capabilities = set(agent.config.capabilities)
            mission_requirements = set(mission.required_capabilities)
            
            if mission_requirements:
                capability_match = len(agent_capabilities & mission_requirements) / len(mission_requirements)
                score += capability_match * 0.6
            else:
                score += 0.3  # Default score if no specific requirements
            
            # Load balancing
            agent_utilization = self.metrics.agent_utilization.get(agent.id, 0.0)
            load_score = 1.0 - (agent_utilization / 100.0)  # Lower utilization = higher score
            score += load_score * 0.3
            
            # Success rate
            if agent.metrics.missions_completed + agent.metrics.missions_failed > 0:
                success_score = agent.metrics.success_rate
                score += success_score * 0.1
            
            scored_agents.append((agent, score))
        
        # Return agent with highest score
        scored_agents.sort(key=lambda x: x[1], reverse=True)
        return scored_agents[0][0] if scored_agents else None
    
    async def execute(self, context: Optional[Dict[str, Any]] = None) -> "SquadResult":
        """Execute all missions in the squad."""
        async with self._execution_lock:
            return await self._execute_internal(context)
    
    async def _execute_internal(self, context: Optional[Dict[str, Any]] = None) -> "SquadResult":
        """Internal execution method."""
        context = context or {}
        self.shared_context.update(context)
        
        # Before hook
        await self._hook_manager.call_hook(
            "before_squad_execute",
            squad=self,
            context=self.shared_context
        )
        
        self.status = SquadStatus.EXECUTING
        self.started_at = datetime.now()
        
        try:
            if self.config.orchestration == OrchestrationPattern.SEQUENTIAL:
                result = await self._execute_sequential()
            elif self.config.orchestration == OrchestrationPattern.PARALLEL:
                result = await self._execute_parallel()
            elif self.config.orchestration == OrchestrationPattern.HIERARCHICAL:
                result = await self._execute_hierarchical()
            elif self.config.orchestration == OrchestrationPattern.ADAPTIVE:
                result = await self._execute_adaptive()
            elif self.config.orchestration == OrchestrationPattern.PIPELINE:
                result = await self._execute_pipeline()
            elif self.config.orchestration == OrchestrationPattern.CONSENSUS:
                result = await self._execute_consensus()
            else:
                raise SquadError(f"Unsupported orchestration pattern: {self.config.orchestration}")
            
            self.status = SquadStatus.COMPLETED
            self.completed_at = datetime.now()
            
            # Update metrics
            self._update_metrics(result)
            
            # After hook
            await self._hook_manager.call_hook(
                "after_squad_execute",
                squad=self,
                result=result,
                context=self.shared_context
            )
            
            return result
            
        except Exception as e:
            self.status = SquadStatus.FAILED
            self.completed_at = datetime.now()
            raise SquadError(f"Squad execution failed: {e}")
    
    async def _execute_sequential(self) -> "SquadResult":
        """Execute missions sequentially."""
        results = []
        
        for mission in self.missions:
            if mission.status != MissionStatus.CREATED:
                continue
            
            # Find available agent
            available_agents = self.get_available_agents()
            if not available_agents:
                raise SquadError("No available agents for sequential execution")
            
            agent = self._find_best_agent_for_mission(mission, available_agents)
            if not agent:
                raise SquadError(f"No suitable agent found for mission {mission.id}")
            
            # Execute mission
            result = await self._execute_mission_with_agent(mission, agent)
            results.append(result)
            
            if not result.success and not self.config.retry_failed_missions:
                break
        
        return SquadResult(
            squad_id=self.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=self._get_execution_time()
        )
    
    async def _execute_parallel(self) -> "SquadResult":
        """Execute missions in parallel."""
        # Auto-assign missions to agents
        assignments = self.auto_assign_missions()
        
        if not assignments:
            return SquadResult(
                squad_id=self.id,
                success=True,
                results=[],
                execution_time=0.0
            )
        
        # Execute missions concurrently
        tasks = []
        for mission, agent in assignments:
            task = asyncio.create_task(self._execute_mission_with_agent(mission, agent))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        mission_results = []
        for result in results:
            if isinstance(result, Exception):
                mission_results.append(MissionResult(
                    mission_id="unknown",
                    status=MissionStatus.FAILED,
                    success=False,
                    error=str(result)
                ))
            else:
                mission_results.append(result)
        
        return SquadResult(
            squad_id=self.id,
            success=all(r.success for r in mission_results),
            results=mission_results,
            execution_time=self._get_execution_time()
        )
    
    async def _execute_hierarchical(self) -> "SquadResult":
        """Execute missions with hierarchical coordination."""
        # Find coordinator agent
        coordinator = None
        for agent in self.agents:
            if "coordination" in agent.config.capabilities:
                coordinator = agent
                break
        
        if not coordinator:
            # Fallback to sequential execution
            return await self._execute_sequential()
        
        # Coordinator plans and delegates missions
        plan = await self._create_execution_plan(coordinator)
        
        # Execute according to plan
        results = []
        for phase in plan:
            phase_results = await self._execute_phase(phase)
            results.extend(phase_results)
        
        return SquadResult(
            squad_id=self.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=self._get_execution_time()
        )
    
    async def _execute_adaptive(self) -> "SquadResult":
        """Execute missions with adaptive orchestration."""
        # Start with parallel execution for independent missions
        independent_missions = [m for m in self.missions if not m.dependencies]
        dependent_missions = [m for m in self.missions if m.dependencies]
        
        results = []
        
        # Execute independent missions in parallel
        if independent_missions:
            parallel_result = await self._execute_missions_parallel(independent_missions)
            results.extend(parallel_result.results)
        
        # Execute dependent missions sequentially or in phases
        if dependent_missions:
            sequential_result = await self._execute_missions_sequential(dependent_missions)
            results.extend(sequential_result.results)
        
        return SquadResult(
            squad_id=self.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=self._get_execution_time()
        )
    
    async def _execute_pipeline(self) -> "SquadResult":
        """Execute missions in pipeline pattern."""
        # Sort missions by dependencies to create pipeline stages
        pipeline_stages = self._create_pipeline_stages()
        
        results = []
        pipeline_data = {}
        
        for stage_missions in pipeline_stages:
            stage_results = []
            
            # Execute stage missions in parallel
            tasks = []
            for mission in stage_missions:
                # Add pipeline data to mission context
                mission.add_context("pipeline_data", pipeline_data)
                
                agent = self._find_best_agent_for_mission(mission, self.get_available_agents())
                if agent:
                    task = asyncio.create_task(self._execute_mission_with_agent(mission, agent))
                    tasks.append(task)
            
            if tasks:
                stage_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process stage results and update pipeline data
                for i, result in enumerate(stage_results):
                    if isinstance(result, MissionResult) and result.success:
                        pipeline_data[f"stage_{len(results)}_mission_{i}"] = result.result
                
                results.extend([r for r in stage_results if isinstance(r, MissionResult)])
        
        return SquadResult(
            squad_id=self.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=self._get_execution_time(),
            metadata={"pipeline_data": pipeline_data}
        )
    
    async def _execute_consensus(self) -> "SquadResult":
        """Execute missions with consensus-based decision making."""
        # For each mission, get multiple agent opinions and reach consensus
        results = []
        
        for mission in self.missions:
            if len(self.agents) < 2:
                # Fallback to single agent execution
                agent = self.agents[0] if self.agents else None
                if agent:
                    result = await self._execute_mission_with_agent(mission, agent)
                    results.append(result)
                continue
            
            # Get opinions from multiple agents
            opinions = []
            for agent in self.agents[:3]:  # Limit to 3 agents for consensus
                try:
                    # Get agent's analysis/opinion on the mission
                    opinion = await agent.think(
                        f"Analyze this mission and provide your approach: {mission.objective}",
                        context={"mission": mission.dict()}
                    )
                    opinions.append((agent, opinion))
                except Exception as e:
                    print(f"Failed to get opinion from agent {agent.id}: {e}")
            
            # Select best approach based on consensus or vote
            if opinions:
                best_agent, best_approach = self._select_consensus_approach(opinions, mission)
                
                # Execute with consensus approach
                mission.add_context("consensus_approach", best_approach)
                result = await self._execute_mission_with_agent(mission, best_agent)
                results.append(result)
        
        return SquadResult(
            squad_id=self.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=self._get_execution_time()
        )
    
    def _select_consensus_approach(self, opinions: List[tuple], mission: Mission) -> tuple:
        """Select the best approach from multiple agent opinions."""
        # Simple implementation - could be more sophisticated
        # For now, select the agent with highest success rate
        best_agent = None
        best_score = 0.0
        best_approach = ""
        
        for agent, approach in opinions:
            score = agent.metrics.success_rate
            if score > best_score:
                best_score = score
                best_agent = agent
                best_approach = approach
        
        return best_agent or opinions[0][0], best_approach or opinions[0][1]
    
    async def _execute_mission_with_agent(self, mission: Mission, agent: Agent) -> MissionResult:
        """Execute a single mission with an agent."""
        try:
            # Assign mission to agent
            self.assign_mission_to_agent(mission, agent)
            
            # Execute mission steps
            while mission.get_next_step():
                current_step = mission.get_next_step()
                if not current_step:
                    break
                
                mission.start_step(current_step.id)
                
                # Agent executes the step
                step_context = {
                    "mission": mission.dict(),
                    "step": current_step.dict(),
                    "shared_context": self.shared_context,
                    "shared_memory": self.shared_memory
                }
                
                try:
                    # Get agent's response for the step
                    response = await agent.think(
                        f"Execute step: {current_step.description}\nMission: {mission.objective}",
                        context=step_context
                    )
                    
                    mission.complete_step(current_step.id, response)
                    
                except Exception as e:
                    mission.fail_step(current_step.id, str(e))
                    break
            
            # Check if all steps completed successfully
            all_completed = all(step.status == MissionStatus.COMPLETED for step in mission.steps)
            
            if all_completed:
                # Collect step results
                step_results = {step.name: step.result for step in mission.steps}
                mission.complete(result=step_results, outputs=step_results)
                
                # Update squad tracking
                self.completed_missions.append(mission.id)
                self.metrics.missions_completed += 1
            else:
                mission.fail("Not all steps completed successfully")
                self.failed_missions.append(mission.id)
                self.metrics.missions_failed += 1
            
            # Remove from current missions
            if mission.id in self.current_missions:
                del self.current_missions[mission.id]
            
            return mission.result
            
        except Exception as e:
            mission.fail(str(e))
            if mission.id in self.current_missions:
                del self.current_missions[mission.id]
            self.failed_missions.append(mission.id)
            self.metrics.missions_failed += 1
            
            return MissionResult(
                mission_id=mission.id,
                status=MissionStatus.FAILED,
                success=False,
                error=str(e)
            )
    
    def _create_pipeline_stages(self) -> List[List[Mission]]:
        """Create pipeline stages based on mission dependencies."""
        stages = []
        remaining_missions = self.missions.copy()
        completed_mission_ids = set()
        
        while remaining_missions:
            # Find missions with satisfied dependencies
            current_stage = []
            for mission in remaining_missions[:]:
                if all(dep_id in completed_mission_ids for dep_id in mission.dependencies):
                    current_stage.append(mission)
                    remaining_missions.remove(mission)
            
            if not current_stage:
                # If no missions can be executed, there might be circular dependencies
                # Add remaining missions to final stage
                stages.append(remaining_missions)
                break
            
            stages.append(current_stage)
            completed_mission_ids.update(mission.id for mission in current_stage)
        
        return stages
    
    def _get_execution_time(self) -> float:
        """Get current execution time."""
        if not self.started_at:
            return 0.0
        
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    def _update_metrics(self, result: "SquadResult") -> None:
        """Update squad metrics after execution."""
        self.metrics.total_execution_time += result.execution_time
        
        if self.metrics.missions_completed + self.metrics.missions_failed > 0:
            self.metrics.average_execution_time = (
                self.metrics.total_execution_time / 
                (self.metrics.missions_completed + self.metrics.missions_failed)
            )
        
        self.metrics.update_success_rate()
    
    def get_status(self) -> Dict[str, Any]:
        """Get squad status."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "agents": len(self.agents),
            "missions": len(self.missions),
            "current_missions": len(self.current_missions),
            "completed_missions": len(self.completed_missions),
            "failed_missions": len(self.failed_missions),
            "metrics": self.metrics.dict(),
            "execution_time": self._get_execution_time()
        }


class SquadResult(BaseModel):
    """Result of squad execution."""
    squad_id: str
    success: bool
    results: List[MissionResult]
    execution_time: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
