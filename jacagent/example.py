"""
Comprehensive JacAgent Example
============================

This example demonstrates the full capabilities of the JacAgent framework:
- Multiple agents with different roles and capabilities
- Complex missions with dependencies and steps
- Plugin system with built-in plugins
- Advanced orchestration patterns
- Memory management and tool usage
"""

import asyncio
from typing import Dict, Any

from jacagent import Agent, Squad, Mission
from jacagent.core.llm import LLMFactory
from jacagent.core.memory import MemoryManager
from jacagent.core.tools import ToolRegistry
from jacagent.plugins.registry import PluginRegistry
from jacagent.plugins.builtin import LoggingPlugin, MetricsPlugin, RetryPlugin, ValidationPlugin
from jacagent.config import GlobalConfig, LLMConfig, MemoryConfig


async def main():
    """Main example function."""
    print("🚀 JacAgent Framework - Comprehensive Example")
    print("=" * 50)
    
    # Initialize configuration
    config = GlobalConfig(
        llm=LLMConfig(
            default_provider="openai",
            default_model="gpt-4",
            temperature=0.7,
            max_tokens=2000
        ),
        memory=MemoryConfig(
            backend="local",
            max_entries=1000
        )
    )
    
    # Initialize plugin registry and load built-in plugins
    plugin_registry = PluginRegistry()
    plugin_registry.register_plugin(LoggingPlugin())
    plugin_registry.register_plugin(MetricsPlugin())
    plugin_registry.register_plugin(RetryPlugin())
    plugin_registry.register_plugin(ValidationPlugin())
    
    print("✅ Plugins loaded successfully")
    
    # Create LLM instances
    openai_llm = LLMFactory.create("openai", model="gpt-4")
    
    # Create memory managers
    memory_manager = MemoryManager("local")
    
    # Initialize tool registry
    tool_registry = ToolRegistry()
    
    # Create agents with different roles and capabilities
    print("\n🤖 Creating Agents...")
    
    # Research Agent
    researcher = Agent.create_researcher(
        name="dr_research",
        llm=openai_llm,
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        config={
            "capabilities": ["research", "analysis", "web_search"],
            "expertise": "scientific research and data analysis",
            "working_style": "thorough and methodical"
        }
    )
    
    # Writer Agent
    writer = Agent.create_writer(
        name="writer_pro",
        llm=openai_llm,
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        config={
            "capabilities": ["writing", "editing", "storytelling"],
            "expertise": "technical writing and documentation",
            "style": "clear and engaging"
        }
    )
    
    # Analyst Agent
    analyst = Agent.create_analyst(
        name="data_analyst",
        llm=openai_llm,
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        config={
            "capabilities": ["analysis", "visualization", "statistics"],
            "expertise": "data analysis and insights",
            "tools": ["calculator", "data_processor"]
        }
    )
    
    # Reviewer Agent
    reviewer = Agent.create_reviewer(
        name="quality_reviewer",
        llm=openai_llm,
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        config={
            "capabilities": ["review", "quality_assurance", "validation"],
            "expertise": "content review and quality control",
            "standards": "high quality and accuracy"
        }
    )
    
    print(f"✅ Created {len([researcher, writer, analyst, reviewer])} agents")
    
    # Create complex missions with dependencies
    print("\n📋 Creating Missions...")
    
    # Mission 1: Research Phase
    research_mission = Mission.create_research_mission(
        objective="Conduct comprehensive research on artificial intelligence trends in 2024",
        description="Research the latest developments, key players, and emerging trends in AI",
        requirements=[
            "Identify top 10 AI trends for 2024",
            "Research key companies and their AI initiatives", 
            "Analyze market impact and predictions",
            "Gather statistical data and expert opinions"
        ],
        deliverables=["research_report", "trend_analysis", "market_data"]
    )
    
    # Mission 2: Analysis Phase (depends on research)
    analysis_mission = Mission.create_analysis_mission(
        objective="Analyze research findings and extract key insights",
        description="Process research data to identify patterns and insights",
        dependencies=[research_mission.id],
        requirements=[
            "Analyze trend data for patterns",
            "Identify key success factors",
            "Calculate market projections",
            "Create data visualizations"
        ],
        deliverables=["analysis_report", "insights_summary", "visualizations"]
    )
    
    # Mission 3: Writing Phase (depends on analysis)
    writing_mission = Mission.create_content_mission(
        objective="Create comprehensive AI trends report for 2024",
        description="Write a detailed report based on research and analysis",
        dependencies=[analysis_mission.id],
        requirements=[
            "Write executive summary",
            "Detail each trend with evidence",
            "Include market analysis section",
            "Add conclusions and recommendations"
        ],
        deliverables=["final_report", "executive_summary", "recommendations"]
    )
    
    # Mission 4: Review Phase (depends on writing)
    review_mission = Mission.create_review_mission(
        objective="Review and validate the AI trends report",
        description="Ensure quality, accuracy, and completeness of the report",
        dependencies=[writing_mission.id],
        requirements=[
            "Check factual accuracy",
            "Validate data and sources",
            "Review writing quality and clarity",
            "Ensure completeness of requirements"
        ],
        deliverables=["review_report", "quality_score", "final_validation"]
    )
    
    print(f"✅ Created {len([research_mission, analysis_mission, writing_mission, review_mission])} missions")
    
    # Create squad with different orchestration patterns
    print("\n👥 Creating Squad...")
    
    # Main squad with adaptive orchestration
    main_squad = Squad(
        name="ai_trends_research_squad",
        description="Multi-agent squad for comprehensive AI trends research",
        agents=[researcher, writer, analyst, reviewer],
        missions=[research_mission, analysis_mission, writing_mission, review_mission],
        config={
            "execution_pattern": "pipeline",  # Use pipeline for dependency-based execution
            "max_concurrent_missions": 2,
            "retry_failed_missions": True,
            "collaboration_enabled": True,
            "load_balancing": True
        }
    )
    
    print("✅ Squad created with pipeline orchestration")
    
    # Execute the squad
    print("\n🎯 Executing Squad...")
    print("This may take a few minutes as agents work through the missions...")
    
    try:
        result = await main_squad.execute()
        
        print("\n📊 Execution Results:")
        print(f"Squad ID: {result.squad_id}")
        print(f"Success: {result.success}")
        print(f"Total Missions: {len(result.results)}")
        print(f"Successful Missions: {sum(1 for r in result.results if r.success)}")
        print(f"Execution Time: {result.execution_time:.2f} seconds")
        
        # Display detailed results
        print("\n📋 Mission Results:")
        for i, mission_result in enumerate(result.results, 1):
            status = "✅ SUCCESS" if mission_result.success else "❌ FAILED"
            print(f"Mission {i}: {status}")
            print(f"  Mission ID: {mission_result.mission_id}")
            print(f"  Status: {mission_result.status.value}")
            if mission_result.result:
                result_preview = str(mission_result.result)[:200] + "..." if len(str(mission_result.result)) > 200 else str(mission_result.result)
                print(f"  Result: {result_preview}")
            if mission_result.error:
                print(f"  Error: {mission_result.error}")
            print()
        
        # Display plugin metrics
        print("\n📈 Plugin Metrics:")
        
        # Metrics Plugin
        metrics_plugin = plugin_registry.get_plugin("metrics")
        if metrics_plugin:
            global_metrics = metrics_plugin.get_global_metrics()
            print("Global Performance:")
            print(f"  Total Requests: {global_metrics['total_requests']}")
            print(f"  Success Rate: {global_metrics['success_rate']:.2%}")
            print(f"  Average Execution Time: {global_metrics['average_execution_time']:.2f}s")
            print(f"  Requests Per Minute: {global_metrics['requests_per_minute']:.1f}")
            
            agent_metrics = metrics_plugin.get_agent_metrics()
            print("\nAgent Performance:")
            for agent_id, metrics in agent_metrics.items():
                print(f"  {agent_id}:")
                print(f"    Missions Completed: {metrics['missions_completed']}")
                print(f"    Success Rate: {metrics['success_rate']:.2%}")
                print(f"    LLM Calls: {metrics['total_llm_calls']}")
                print(f"    Tool Calls: {metrics['total_tool_calls']}")
        
        # Validation Plugin
        validation_plugin = plugin_registry.get_plugin("validation")
        if validation_plugin:
            validation_stats = validation_plugin.get_validation_statistics()
            print("\nValidation Statistics:")
            print(f"  Total Validations: {validation_stats['total_validations']}")
            print(f"  Success Rate: {validation_stats['success_rate']:.2%}")
            print(f"  Warnings: {validation_stats['warning_validations']}")
            print(f"  Failures: {validation_stats['failed_validations']}")
        
        # Retry Plugin
        retry_plugin = plugin_registry.get_plugin("retry")
        if retry_plugin:
            retry_stats = retry_plugin.get_retry_statistics()
            print("\nRetry Statistics:")
            print(f"  Operations with Retries: {retry_stats['operations_with_retries']}")
            print(f"  Circuit Breakers Open: {retry_stats['circuit_breakers_open']}")
        
        print("\n🎉 Squad execution completed successfully!")
        
        # Demonstrate memory retrieval
        print("\n🧠 Memory System Demo:")
        researcher_memories = await researcher.memory_manager.retrieve_memories("short_term", "AI trends")
        print(f"Researcher has {len(researcher_memories)} memories about AI trends")
        
        # Demonstrate tool usage statistics
        print("\n🛠️ Tool Usage Demo:")
        available_tools = tool_registry.list_tools()
        print(f"Available tools: {', '.join(available_tools)}")
        
    except Exception as error:
        print(f"\n❌ Squad execution failed: {error}")
        
        # Show error details from plugins
        validation_plugin = plugin_registry.get_plugin("validation")
        if validation_plugin:
            validation_stats = validation_plugin.get_validation_statistics()
            if validation_stats['recent_errors']:
                print("\nRecent Validation Errors:")
                for error_info in validation_stats['recent_errors'][-3:]:
                    print(f"  {error_info['timestamp']}: {error_info['error']}")
    
    print("\n" + "=" * 50)
    print("🏁 JacAgent Framework Example Complete")


async def demonstrate_orchestration_patterns():
    """Demonstrate different orchestration patterns."""
    print("\n🔀 Orchestration Patterns Demo")
    print("-" * 30)
    
    # Create simple agents and missions for pattern demonstration
    llm = LLMFactory.create("openai", model="gpt-3.5-turbo")
    
    agents = [
        Agent(name=f"agent_{i}", role="assistant", llm=llm)
        for i in range(3)
    ]
    
    missions = [
        Mission(objective=f"Complete task {i}", description=f"Task {i} description")
        for i in range(3)
    ]
    
    patterns = ["sequential", "parallel", "hierarchical", "adaptive", "pipeline", "consensus"]
    
    for pattern in patterns:
        print(f"\n📋 Testing {pattern.title()} Pattern:")
        
        squad = Squad(
            name=f"{pattern}_squad",
            agents=agents.copy(),
            missions=missions.copy(),
            config={"execution_pattern": pattern}
        )
        
        try:
            result = await squad.execute()
            print(f"  ✅ {pattern.title()} execution: {result.success}")
            print(f"  ⏱️  Execution time: {result.execution_time:.2f}s")
        except Exception as e:
            print(f"  ❌ {pattern.title()} execution failed: {e}")


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())
    
    # Uncomment to run orchestration patterns demo
    # asyncio.run(demonstrate_orchestration_patterns())
