"""Orchestration patterns for squad execution."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from jacagent.exceptions import SquadError


class OrchestrationPattern(ABC):
    """Base class for orchestration patterns."""
    
    @abstractmethod
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the orchestration pattern."""
        pass
    
    @abstractmethod
    def validate_configuration(self, squad: Any) -> bool:
        """Validate that squad is properly configured for this pattern."""
        pass


class SequentialPattern(OrchestrationPattern):
    """Sequential execution pattern."""
    
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute missions sequentially."""
        results = []
        
        for mission in squad.missions:
            if mission.status.value != "created":
                continue
            
            # Find available agent
            available_agents = squad.get_available_agents()
            if not available_agents:
                raise SquadError("No available agents for sequential execution")
            
            agent = squad._find_best_agent_for_mission(mission, available_agents)
            if not agent:
                raise SquadError(f"No suitable agent found for mission {mission.id}")
            
            # Execute mission
            result = await squad._execute_mission_with_agent(mission, agent)
            results.append(result)
            
            if not result.success and not squad.config.retry_failed_missions:
                break
        
        from jacagent.core.squad import SquadResult
        return SquadResult(
            squad_id=squad.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=squad._get_execution_time()
        )
    
    def validate_configuration(self, squad: Any) -> bool:
        """Validate squad for sequential execution."""
        return len(squad.agents) >= 1 and len(squad.missions) >= 1


class ParallelPattern(OrchestrationPattern):
    """Parallel execution pattern."""
    
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute missions in parallel."""
        import asyncio
        
        # Auto-assign missions to agents
        assignments = squad.auto_assign_missions()
        
        if not assignments:
            from jacagent.core.squad import SquadResult
            return SquadResult(
                squad_id=squad.id,
                success=True,
                results=[],
                execution_time=0.0
            )
        
        # Execute missions concurrently
        tasks = []
        for mission, agent in assignments:
            task = asyncio.create_task(squad._execute_mission_with_agent(mission, agent))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        from jacagent.core.mission import MissionResult, MissionStatus
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
        
        from jacagent.core.squad import SquadResult
        return SquadResult(
            squad_id=squad.id,
            success=all(r.success for r in mission_results),
            results=mission_results,
            execution_time=squad._get_execution_time()
        )
    
    def validate_configuration(self, squad: Any) -> bool:
        """Validate squad for parallel execution."""
        return len(squad.agents) >= len(squad.missions)


class HierarchicalPattern(OrchestrationPattern):
    """Hierarchical execution pattern with coordinator."""
    
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute with hierarchical coordination."""
        # Find coordinator agent
        coordinator = None
        for agent in squad.agents:
            if "coordination" in agent.config.capabilities:
                coordinator = agent
                break
        
        if not coordinator:
            # Fallback to sequential execution
            sequential = SequentialPattern()
            return await sequential.execute(squad, context)
        
        # Coordinator plans and delegates missions
        plan = await self._create_execution_plan(coordinator, squad)
        
        # Execute according to plan
        results = []
        for phase in plan:
            phase_results = await self._execute_phase(phase, squad)
            results.extend(phase_results)
        
        from jacagent.core.squad import SquadResult
        return SquadResult(
            squad_id=squad.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=squad._get_execution_time()
        )
    
    async def _create_execution_plan(self, coordinator: Any, squad: Any) -> List[List[Any]]:
        """Create execution plan using coordinator."""
        # Simple planning - could be more sophisticated
        return [squad.missions]  # Single phase for now
    
    async def _execute_phase(self, missions: List[Any], squad: Any) -> List[Any]:
        """Execute a phase of missions."""
        results = []
        for mission in missions:
            available_agents = squad.get_available_agents()
            if available_agents:
                agent = squad._find_best_agent_for_mission(mission, available_agents)
                if agent:
                    result = await squad._execute_mission_with_agent(mission, agent)
                    results.append(result)
        return results
    
    def validate_configuration(self, squad: Any) -> bool:
        """Validate squad for hierarchical execution."""
        # Need at least one coordinator
        coordinators = [a for a in squad.agents if "coordination" in a.config.capabilities]
        return len(coordinators) >= 1


class AdaptivePattern(OrchestrationPattern):
    """Adaptive execution pattern that chooses best approach."""
    
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute with adaptive orchestration."""
        # Analyze missions and choose best pattern
        if self._should_use_parallel(squad):
            pattern = ParallelPattern()
        elif self._should_use_hierarchical(squad):
            pattern = HierarchicalPattern()
        else:
            pattern = SequentialPattern()
        
        return await pattern.execute(squad, context)
    
    def _should_use_parallel(self, squad: Any) -> bool:
        """Determine if parallel execution is optimal."""
        # Use parallel if we have enough agents and independent missions
        independent_missions = [m for m in squad.missions if not m.dependencies]
        return len(squad.agents) >= len(independent_missions) and len(independent_missions) > 1
    
    def _should_use_hierarchical(self, squad: Any) -> bool:
        """Determine if hierarchical execution is optimal."""
        # Use hierarchical if we have a coordinator and complex missions
        coordinators = [a for a in squad.agents if "coordination" in a.config.capabilities]
        complex_missions = [m for m in squad.missions if len(m.steps) > 3]
        return len(coordinators) > 0 and len(complex_missions) > 0
    
    def validate_configuration(self, squad: Any) -> bool:
        """Adaptive pattern can work with any valid squad."""
        return len(squad.agents) >= 1 and len(squad.missions) >= 1


class PipelinePattern(OrchestrationPattern):
    """Pipeline execution pattern with data flow."""
    
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute in pipeline stages."""
        # Sort missions by dependencies to create pipeline stages
        pipeline_stages = self._create_pipeline_stages(squad.missions)
        
        results = []
        pipeline_data = {}
        
        for stage_missions in pipeline_stages:
            stage_results = []
            
            # Execute stage missions in parallel
            import asyncio
            tasks = []
            for mission in stage_missions:
                # Add pipeline data to mission context
                mission.add_context("pipeline_data", pipeline_data)
                
                agent = squad._find_best_agent_for_mission(mission, squad.get_available_agents())
                if agent:
                    task = asyncio.create_task(squad._execute_mission_with_agent(mission, agent))
                    tasks.append(task)
            
            if tasks:
                stage_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process stage results and update pipeline data
                from jacagent.core.mission import MissionResult
                for i, result in enumerate(stage_results):
                    if isinstance(result, MissionResult) and result.success:
                        pipeline_data[f"stage_{len(results)}_mission_{i}"] = result.result
                
                results.extend([r for r in stage_results if isinstance(r, MissionResult)])
        
        from jacagent.core.squad import SquadResult
        return SquadResult(
            squad_id=squad.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=squad._get_execution_time(),
            metadata={"pipeline_data": pipeline_data}
        )
    
    def _create_pipeline_stages(self, missions: List[Any]) -> List[List[Any]]:
        """Create pipeline stages based on dependencies."""
        stages = []
        remaining_missions = missions.copy()
        completed_mission_ids = set()
        
        while remaining_missions:
            # Find missions with satisfied dependencies
            current_stage = []
            for mission in remaining_missions[:]:
                if all(dep_id in completed_mission_ids for dep_id in mission.dependencies):
                    current_stage.append(mission)
                    remaining_missions.remove(mission)
            
            if not current_stage:
                # Add remaining missions to final stage
                stages.append(remaining_missions)
                break
            
            stages.append(current_stage)
            completed_mission_ids.update(mission.id for mission in current_stage)
        
        return stages
    
    def validate_configuration(self, squad: Any) -> bool:
        """Validate squad for pipeline execution."""
        # Check if missions have proper dependency structure
        return len(squad.missions) >= 1


class ConsensusPattern(OrchestrationPattern):
    """Consensus-based execution pattern."""
    
    async def execute(self, squad: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute with consensus decision making."""
        results = []
        
        for mission in squad.missions:
            if len(squad.agents) < 2:
                # Fallback to single agent execution
                agent = squad.agents[0] if squad.agents else None
                if agent:
                    result = await squad._execute_mission_with_agent(mission, agent)
                    results.append(result)
                continue
            
            # Get opinions from multiple agents
            opinions = []
            for agent in squad.agents[:3]:  # Limit to 3 agents for consensus
                try:
                    opinion = await agent.think(
                        f"Analyze this mission and provide your approach: {mission.objective}",
                        context={"mission": mission.dict()}
                    )
                    opinions.append((agent, opinion))
                except Exception as e:
                    print(f"Failed to get opinion from agent {agent.id}: {e}")
            
            # Select best approach based on consensus
            if opinions:
                best_agent, best_approach = self._select_consensus_approach(opinions, mission)
                
                # Execute with consensus approach
                mission.add_context("consensus_approach", best_approach)
                result = await squad._execute_mission_with_agent(mission, best_agent)
                results.append(result)
        
        from jacagent.core.squad import SquadResult
        return SquadResult(
            squad_id=squad.id,
            success=all(r.success for r in results),
            results=results,
            execution_time=squad._get_execution_time()
        )
    
    def _select_consensus_approach(self, opinions: List[tuple], mission: Any) -> tuple:
        """Select best approach from opinions."""
        # Simple implementation - select agent with highest success rate
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
    
    def validate_configuration(self, squad: Any) -> bool:
        """Validate squad for consensus execution."""
        return len(squad.agents) >= 2
