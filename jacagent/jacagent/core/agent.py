"""Core Agent implementation for JacAgent framework."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from jacagent.exceptions import AgentError
from jacagent.core.llm import BaseLLM, LLMMessage, LLMConfig, LLMResponse
from jacagent.core.memory import MemoryManager, MemoryType
from jacagent.core.tools import BaseTool, ToolRegistry, ToolResult
from jacagent.plugins.hooks import get_hook_manager
from jacagent.config import get_config


class AgentState(str, Enum):
    """Agent execution states."""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class AgentRole(str, Enum):
    """Predefined agent roles."""
    RESEARCHER = "researcher"
    WRITER = "writer"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    GENERALIST = "generalist"
    CUSTOM = "custom"


class AgentCapability(str, Enum):
    """Agent capabilities."""
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    PLANNING = "planning"
    COORDINATION = "coordination"
    TOOL_USE = "tool_use"
    MEMORY_ACCESS = "memory_access"
    LEARNING = "learning"
    COLLABORATION = "collaboration"


class AgentMetrics(BaseModel):
    """Agent performance metrics."""
    missions_completed: int = 0
    missions_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    tools_used: int = 0
    llm_calls: int = 0
    memory_operations: int = 0
    errors_encountered: int = 0
    success_rate: float = 0.0
    
    def update_success_rate(self):
        """Update success rate calculation."""
        total = self.missions_completed + self.missions_failed
        if total > 0:
            self.success_rate = self.missions_completed / total


class AgentConfig(BaseModel):
    """Configuration for an agent."""
    role: Union[AgentRole, str] = AgentRole.GENERALIST
    persona: str = Field(description="Agent's personality and behavior")
    capabilities: List[Union[AgentCapability, str]] = Field(default_factory=list)
    max_iterations: int = Field(default=10, gt=0)
    timeout: int = Field(default=300, gt=0)  # seconds
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    enable_memory: bool = Field(default=True)
    enable_learning: bool = Field(default=True)
    enable_collaboration: bool = Field(default=True)
    tool_names: List[str] = Field(default_factory=list)
    custom_instructions: str = Field(default="")
    plugins: List[str] = Field(default_factory=list)


class Agent(BaseModel):
    """Enhanced agent with dynamic capabilities and extensive customization."""
    
    # Core Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Agent name")
    config: AgentConfig = Field(description="Agent configuration")
    
    # State Management
    state: AgentState = Field(default=AgentState.IDLE)
    current_mission: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    
    # Performance Tracking
    metrics: AgentMetrics = Field(default_factory=AgentMetrics)
    
    # Internal Components (not included in serialization)
    _llm: Optional[BaseLLM] = None
    _memory: Optional[MemoryManager] = None
    _tools: Dict[str, BaseTool] = {}
    _hook_manager = None
    _conversation_history: List[LLMMessage] = []
    
    class Config:
        arbitrary_types_allowed = True
        exclude = {"_llm", "_memory", "_tools", "_hook_manager", "_conversation_history"}
    
    def __init__(self, **data):
        super().__init__(**data)
        self._hook_manager = get_hook_manager()
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize agent components."""
        # Initialize memory if enabled
        if self.config.enable_memory:
            from jacagent.core.memory import get_memory_manager
            self._memory = get_memory_manager()
        
        # Initialize tools
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize agent tools."""
        from jacagent.core.tools import get_tool_registry
        
        tool_registry = get_tool_registry()
        
        for tool_name in self.config.tool_names:
            try:
                tool = tool_registry.create_tool(tool_name)
                self._tools[tool_name] = tool
            except Exception as e:
                print(f"Failed to initialize tool {tool_name}: {e}")
    
    def set_llm(self, llm: BaseLLM) -> None:
        """Set the LLM for this agent."""
        self._llm = llm
    
    async def think(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response using the agent's LLM."""
        if not self._llm:
            raise AgentError("No LLM configured for agent")
        
        context = context or {}
        self.state = AgentState.THINKING
        
        try:
            # Build conversation context
            messages = await self._build_conversation_context(input_text, context)
            
            # Create LLM config
            llm_config = LLMConfig(
                model=self._llm.config.get("model", "gpt-4"),
                temperature=self.config.temperature,
                timeout=self.config.timeout
            )
            
            # Call LLM with hooks
            response = await self._llm.call_with_hooks(messages, llm_config, context)
            
            # Update conversation history
            self._conversation_history.extend([
                LLMMessage(role="user", content=input_text),
                LLMMessage(role="assistant", content=response.content)
            ])
            
            # Update metrics
            self.metrics.llm_calls += 1
            
            # Store in memory if enabled
            if self._memory:
                await self._memory.store_short_term(
                    f"conversation_{len(self._conversation_history)}",
                    {"input": input_text, "output": response.content},
                    metadata={"timestamp": datetime.now().isoformat()}
                )
                self.metrics.memory_operations += 1
            
            self.state = AgentState.IDLE
            self.last_active = datetime.now()
            
            return response.content
            
        except Exception as e:
            self.state = AgentState.ERROR
            self.metrics.errors_encountered += 1
            raise AgentError(f"Agent thinking failed: {e}")
    
    async def _build_conversation_context(
        self, 
        input_text: str, 
        context: Dict[str, Any]
    ) -> List[LLMMessage]:
        """Build conversation context with system prompt and history."""
        messages = []
        
        # System prompt
        system_prompt = self._build_system_prompt(context)
        messages.append(LLMMessage(role="system", content=system_prompt))
        
        # Add recent conversation history (limited)
        recent_history = self._conversation_history[-10:]  # Last 10 messages
        messages.extend(recent_history)
        
        # Add current input
        messages.append(LLMMessage(role="user", content=input_text))
        
        return messages
    
    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt based on agent configuration."""
        prompt_parts = [
            f"You are an AI agent with the role of {self.config.role}.",
            f"Your persona: {self.config.persona}",
        ]
        
        if self.config.capabilities:
            capabilities_str = ", ".join(self.config.capabilities)
            prompt_parts.append(f"Your capabilities include: {capabilities_str}")
        
        if self.config.custom_instructions:
            prompt_parts.append(f"Additional instructions: {self.config.custom_instructions}")
        
        if self._tools:
            tools_str = ", ".join(self._tools.keys())
            prompt_parts.append(f"Available tools: {tools_str}")
        
        # Add context information
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            prompt_parts.append(f"Current context:\n{context_str}")
        
        return "\n\n".join(prompt_parts)
    
    async def use_tool(
        self, 
        tool_name: str, 
        *args, 
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ToolResult:
        """Use a tool."""
        if tool_name not in self._tools:
            raise AgentError(f"Tool '{tool_name}' not available to agent")
        
        context = context or {}
        self.state = AgentState.ACTING
        
        try:
            tool = self._tools[tool_name]
            result = await tool.execute_with_hooks(*args, context=context, **kwargs)
            
            # Update metrics
            self.metrics.tools_used += 1
            
            # Store tool usage in memory if enabled
            if self._memory:
                await self._memory.store_episodic(
                    f"tool_use_{tool_name}_{int(datetime.now().timestamp())}",
                    {
                        "tool": tool_name,
                        "args": args,
                        "kwargs": kwargs,
                        "result": result.dict()
                    },
                    metadata={"timestamp": datetime.now().isoformat()}
                )
                self.metrics.memory_operations += 1
            
            self.state = AgentState.IDLE
            self.last_active = datetime.now()
            
            return result
            
        except Exception as e:
            self.state = AgentState.ERROR
            self.metrics.errors_encountered += 1
            raise AgentError(f"Tool execution failed: {e}")
    
    async def remember(self, key: str) -> Optional[Any]:
        """Retrieve from memory."""
        if not self._memory:
            return None
        
        try:
            value = await self._memory.retrieve(key)
            self.metrics.memory_operations += 1
            return value
        except Exception as e:
            raise AgentError(f"Memory retrieval failed: {e}")
    
    async def memorize(
        self, 
        key: str, 
        value: Any, 
        memory_type: MemoryType = MemoryType.WORKING,
        importance: float = 0.5
    ) -> None:
        """Store in memory."""
        if not self._memory:
            return
        
        try:
            await self._memory.store(key, value, memory_type, importance)
            self.metrics.memory_operations += 1
        except Exception as e:
            raise AgentError(f"Memory storage failed: {e}")
    
    async def learn_from_experience(self, experience: Dict[str, Any]) -> None:
        """Learn from an experience."""
        if not self.config.enable_learning or not self._memory:
            return
        
        try:
            # Store experience in long-term memory
            experience_key = f"experience_{int(datetime.now().timestamp())}"
            await self._memory.store_long_term(
                experience_key,
                experience,
                importance=0.8,  # High importance for learning
                metadata={"type": "learning_experience"}
            )
            
            # Update metrics
            self.metrics.memory_operations += 1
            
        except Exception as e:
            raise AgentError(f"Learning failed: {e}")
    
    def add_capability(self, capability: Union[AgentCapability, str]) -> None:
        """Add a capability to the agent."""
        if capability not in self.config.capabilities:
            self.config.capabilities.append(capability)
    
    def remove_capability(self, capability: Union[AgentCapability, str]) -> None:
        """Remove a capability from the agent."""
        if capability in self.config.capabilities:
            self.config.capabilities.remove(capability)
    
    def add_tool(self, tool_name: str) -> None:
        """Add a tool to the agent."""
        if tool_name not in self.config.tool_names:
            self.config.tool_names.append(tool_name)
            
            # Initialize the tool
            from jacagent.core.tools import get_tool_registry
            tool_registry = get_tool_registry()
            
            try:
                tool = tool_registry.create_tool(tool_name)
                self._tools[tool_name] = tool
            except Exception as e:
                print(f"Failed to add tool {tool_name}: {e}")
    
    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from the agent."""
        if tool_name in self.config.tool_names:
            self.config.tool_names.remove(tool_name)
        
        if tool_name in self._tools:
            del self._tools[tool_name]
    
    def update_persona(self, persona: str) -> None:
        """Update agent persona."""
        self.config.persona = persona
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "role": self.config.role,
            "capabilities": self.config.capabilities,
            "tools": list(self._tools.keys()),
            "metrics": self.metrics.dict(),
            "last_active": self.last_active.isoformat(),
            "conversation_length": len(self._conversation_history)
        }
    
    # Factory methods for common agent types
    @classmethod
    def researcher(
        cls, 
        name: str = "Researcher",
        expertise: str = "general research",
        **kwargs
    ) -> "Agent":
        """Create a researcher agent."""
        config = AgentConfig(
            role=AgentRole.RESEARCHER,
            persona=f"Expert researcher specializing in {expertise}. Methodical, thorough, and fact-oriented.",
            capabilities=[
                AgentCapability.RESEARCH,
                AgentCapability.ANALYSIS,
                AgentCapability.TOOL_USE
            ],
            tool_names=["web_scraper", "file_system"],
            **kwargs
        )
        
        return cls(name=name, config=config)
    
    @classmethod
    def writer(
        cls, 
        name: str = "Writer",
        style: str = "professional",
        **kwargs
    ) -> "Agent":
        """Create a writer agent."""
        config = AgentConfig(
            role=AgentRole.WRITER,
            persona=f"Professional writer with {style} style. Creative, articulate, and detail-oriented.",
            capabilities=[
                AgentCapability.WRITING,
                AgentCapability.ANALYSIS,
                AgentCapability.MEMORY_ACCESS
            ],
            tool_names=["file_system"],
            **kwargs
        )
        
        return cls(name=name, config=config)
    
    @classmethod
    def analyst(
        cls, 
        name: str = "Analyst",
        domain: str = "data analysis",
        **kwargs
    ) -> "Agent":
        """Create an analyst agent."""
        config = AgentConfig(
            role=AgentRole.ANALYST,
            persona=f"Expert analyst in {domain}. Logical, precise, and insights-driven.",
            capabilities=[
                AgentCapability.ANALYSIS,
                AgentCapability.RESEARCH,
                AgentCapability.TOOL_USE
            ],
            tool_names=["calculator", "file_system"],
            **kwargs
        )
        
        return cls(name=name, config=config)
    
    @classmethod
    def reviewer(
        cls, 
        name: str = "Reviewer",
        criteria: str = "quality and accuracy",
        **kwargs
    ) -> "Agent":
        """Create a reviewer agent."""
        config = AgentConfig(
            role=AgentRole.REVIEWER,
            persona=f"Thorough reviewer focused on {criteria}. Critical, fair, and improvement-oriented.",
            capabilities=[
                AgentCapability.ANALYSIS,
                AgentCapability.WRITING,
                AgentCapability.MEMORY_ACCESS
            ],
            tool_names=["file_system"],
            **kwargs
        )
        
        return cls(name=name, config=config)
    
    @classmethod
    def create(
        cls,
        role: str,
        persona: str,
        name: Optional[str] = None,
        **kwargs
    ) -> "Agent":
        """Create a custom agent."""
        config = AgentConfig(
            role=role,
            persona=persona,
            **kwargs
        )
        
        return cls(name=name or f"Agent_{role}", config=config)
