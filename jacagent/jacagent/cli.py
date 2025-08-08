"""Command-line interface for JacAgent."""

import asyncio
import json
import os
import sys
import typer
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import yaml

from jacagent import Agent, Squad, Mission
from jacagent.core.llm import LLMFactory
from jacagent.config import GlobalConfig
from jacagent.plugins.registry import PluginRegistry

app = typer.Typer(
    name="jacagent",
    help="JacAgent - Advanced Multi-Agent AI Framework",
    rich_markup_mode="rich"
)

console = Console()


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name"),
    template: str = typer.Option("basic", help="Project template (basic, research, data-analysis)"),
    llm_provider: str = typer.Option("openai", help="Default LLM provider"),
    python_version: str = typer.Option("3.10", help="Python version")
):
    """Initialize a new JacAgent project."""
    project_dir = Path(name)
    
    if project_dir.exists():
        console.print(f"[red]Directory {name} already exists[/red]")
        raise typer.Exit(1)
    
    console.print(f"[green]Creating JacAgent project: {name}[/green]")
    
    # Create project structure
    project_dir.mkdir()
    (project_dir / "agents").mkdir()
    (project_dir / "missions").mkdir()
    (project_dir / "plugins").mkdir()
    (project_dir / "config").mkdir()
    
    # Create project files
    _create_project_files(project_dir, name, template, llm_provider, python_version)
    
    console.print(f"[green]✓ Project {name} created successfully![/green]")
    console.print(f"[blue]Next steps:[/blue]")
    console.print(f"  cd {name}")
    console.print(f"  pip install -r requirements.txt")
    console.print(f"  jacagent run")


@app.command()
def run(
    config_file: str = typer.Option("config/squad.yaml", help="Squad configuration file"),
    debug: bool = typer.Option(False, help="Enable debug mode"),
    watch: bool = typer.Option(False, help="Watch for file changes")
):
    """Run a squad configuration."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        console.print(f"[red]Configuration file {config_file} not found[/red]")
        raise typer.Exit(1)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running squad...", total=None)
            
            result = asyncio.run(_run_squad_from_config(config_path, debug))
            
            progress.update(task, description="[green]Squad execution completed[/green]")
        
        # Display results
        _display_squad_results(result)
        
    except Exception as e:
        console.print(f"[red]Error running squad: {e}[/red]")
        if debug:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def create_agent(
    name: str = typer.Argument(..., help="Agent name"),
    role: str = typer.Option("assistant", help="Agent role"),
    model: str = typer.Option("gpt-4", help="LLM model"),
    capabilities: List[str] = typer.Option([], help="Agent capabilities"),
    interactive: bool = typer.Option(False, help="Interactive agent creation")
):
    """Create a new agent configuration."""
    if interactive:
        _create_agent_interactive()
    else:
        _create_agent_from_params(name, role, model, capabilities)


@app.command()
def create_mission(
    name: str = typer.Argument(..., help="Mission name"),
    objective: str = typer.Option("", help="Mission objective"),
    mission_type: str = typer.Option("simple", help="Mission type"),
    interactive: bool = typer.Option(False, help="Interactive mission creation")
):
    """Create a new mission configuration."""
    if interactive:
        _create_mission_interactive()
    else:
        _create_mission_from_params(name, objective, mission_type)


@app.command()
def list_plugins():
    """List available plugins."""
    registry = PluginRegistry()
    plugins = registry.list_plugins()
    
    table = Table(title="Available Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Description")
    
    for plugin in plugins:
        status = "✓ Loaded" if plugin.is_loaded else "○ Available"
        table.add_row(
            plugin.name,
            plugin.version,
            status,
            plugin.description
        )
    
    console.print(table)


@app.command()
def install_plugin(name: str = typer.Argument(..., help="Plugin name")):
    """Install a plugin."""
    registry = PluginRegistry()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Installing plugin {name}...", total=None)
            
            registry.install_plugin(name)
            
            progress.update(task, description=f"[green]Plugin {name} installed[/green]")
        
        console.print(f"[green]✓ Plugin {name} installed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]Error installing plugin {name}: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate_config(
    config_file: str = typer.Argument(..., help="Configuration file to validate")
):
    """Validate a configuration file."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        console.print(f"[red]Configuration file {config_file} not found[/red]")
        raise typer.Exit(1)
    
    try:
        if config_path.suffix == '.yaml':
            with open(config_path) as f:
                config_data = yaml.safe_load(f)
        else:
            with open(config_path) as f:
                config_data = json.load(f)
        
        # Validate configuration structure
        errors = _validate_config_structure(config_data)
        
        if errors:
            console.print(f"[red]Configuration validation failed:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            raise typer.Exit(1)
        else:
            console.print(f"[green]✓ Configuration is valid[/green]")
            
    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def monitor(
    squad_id: Optional[str] = typer.Option(None, help="Squad ID to monitor"),
    refresh: int = typer.Option(5, help="Refresh interval in seconds")
):
    """Monitor squad execution in real-time."""
    console.print("[blue]Starting JacAgent monitor...[/blue]")
    
    # This would connect to a monitoring service in a real implementation
    console.print("[yellow]Monitor functionality requires JacAgent server to be running[/yellow]")


def _create_project_files(
    project_dir: Path,
    name: str,
    template: str,
    llm_provider: str,
    python_version: str
):
    """Create project files based on template."""
    
    # requirements.txt
    requirements = [
        "jacagent",
        f"{llm_provider}>=1.0.0",
        "pydantic>=2.0.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "pyyaml>=6.0"
    ]
    
    (project_dir / "requirements.txt").write_text("\n".join(requirements))
    
    # pyproject.toml
    pyproject = f"""[tool.poetry]
name = "{name}"
version = "0.1.0"
description = "JacAgent project: {name}"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^{python_version}"
jacagent = "^0.1.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
"""
    (project_dir / "pyproject.toml").write_text(pyproject)
    
    # Basic squad configuration
    squad_config = {
        "squad": {
            "name": f"{name}_squad",
            "description": f"Squad for {name} project",
            "config": {
                "execution_pattern": "adaptive",
                "max_concurrent_missions": 3,
                "retry_failed_missions": True
            }
        },
        "agents": [
            {
                "name": "researcher",
                "role": "research_specialist",
                "config": {
                    "llm_provider": llm_provider,
                    "model": "gpt-4",
                    "capabilities": ["research", "analysis"]
                }
            }
        ],
        "missions": [
            {
                "name": "example_mission",
                "type": "simple",
                "objective": "Complete the example mission",
                "description": "This is an example mission to get you started"
            }
        ]
    }
    
    (project_dir / "config" / "squad.yaml").write_text(yaml.dump(squad_config))
    
    # Main script
    main_script = f'''"""Main script for {name} project."""

import asyncio
from jacagent import Agent, Squad, Mission
from jacagent.core.llm import LLMFactory

async def main():
    """Main function."""
    # Create LLM
    llm = LLMFactory.create("{llm_provider}", model="gpt-4")
    
    # Create agent
    agent = Agent(
        name="assistant",
        role="helpful_assistant",
        llm=llm
    )
    
    # Create mission
    mission = Mission(
        objective="Say hello and introduce yourself",
        description="A simple greeting mission"
    )
    
    # Create squad
    squad = Squad(
        name="{name}_squad",
        agents=[agent],
        missions=[mission]
    )
    
    # Execute
    result = await squad.execute()
    print(f"Squad execution result: {{result}}")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    (project_dir / "main.py").write_text(main_script)
    
    # README.md
    readme = f"""# {name}

A JacAgent project for {template} workflows.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your environment variables (if using external APIs):
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```

3. Run the project:
   ```bash
   python main.py
   # or
   jacagent run
   ```

## Project Structure

- `agents/` - Agent configurations
- `missions/` - Mission definitions
- `plugins/` - Custom plugins
- `config/` - Configuration files
- `main.py` - Main entry point

## Customization

Edit `config/squad.yaml` to customize your squad configuration.
"""
    
    (project_dir / "README.md").write_text(readme)


async def _run_squad_from_config(config_path: Path, debug: bool) -> Dict[str, Any]:
    """Run squad from configuration file."""
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    # Create agents
    agents = []
    for agent_config in config_data.get("agents", []):
        llm = LLMFactory.create(
            agent_config["config"]["llm_provider"],
            model=agent_config["config"]["model"]
        )
        
        agent = Agent(
            name=agent_config["name"],
            role=agent_config["role"],
            llm=llm
        )
        agents.append(agent)
    
    # Create missions
    missions = []
    for mission_config in config_data.get("missions", []):
        mission = Mission(
            objective=mission_config["objective"],
            description=mission_config.get("description", ""),
            mission_type=mission_config.get("type", "simple")
        )
        missions.append(mission)
    
    # Create squad
    squad_config = config_data["squad"]
    squad = Squad(
        name=squad_config["name"],
        agents=agents,
        missions=missions
    )
    
    # Execute
    return await squad.execute()


def _display_squad_results(result: Dict[str, Any]):
    """Display squad execution results."""
    table = Table(title="Squad Execution Results")
    table.add_column("Mission", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Result")
    
    for mission_result in result.get("results", []):
        status = "✓ Success" if mission_result.get("success") else "✗ Failed"
        table.add_row(
            mission_result.get("mission_id", "Unknown"),
            status,
            str(mission_result.get("result", ""))[:100] + "..." if len(str(mission_result.get("result", ""))) > 100 else str(mission_result.get("result", ""))
        )
    
    console.print(table)


def _create_agent_interactive():
    """Create agent interactively."""
    console.print("[blue]Creating new agent...[/blue]")
    
    name = typer.prompt("Agent name")
    role = typer.prompt("Agent role", default="assistant")
    model = typer.prompt("LLM model", default="gpt-4")
    
    agent_config = {
        "name": name,
        "role": role,
        "config": {
            "llm_provider": "openai",
            "model": model,
            "capabilities": []
        }
    }
    
    # Save to file
    agent_file = Path("agents") / f"{name}.yaml"
    agent_file.parent.mkdir(exist_ok=True)
    
    with open(agent_file, "w") as f:
        yaml.dump(agent_config, f)
    
    console.print(f"[green]✓ Agent {name} created in {agent_file}[/green]")


def _create_agent_from_params(name: str, role: str, model: str, capabilities: List[str]):
    """Create agent from parameters."""
    agent_config = {
        "name": name,
        "role": role,
        "config": {
            "llm_provider": "openai",
            "model": model,
            "capabilities": capabilities
        }
    }
    
    agent_file = Path("agents") / f"{name}.yaml"
    agent_file.parent.mkdir(exist_ok=True)
    
    with open(agent_file, "w") as f:
        yaml.dump(agent_config, f)
    
    console.print(f"[green]✓ Agent {name} created[/green]")


def _create_mission_interactive():
    """Create mission interactively."""
    console.print("[blue]Creating new mission...[/blue]")
    
    name = typer.prompt("Mission name")
    objective = typer.prompt("Mission objective")
    mission_type = typer.prompt("Mission type", default="simple")
    
    mission_config = {
        "name": name,
        "objective": objective,
        "type": mission_type,
        "description": f"Mission: {objective}"
    }
    
    mission_file = Path("missions") / f"{name}.yaml"
    mission_file.parent.mkdir(exist_ok=True)
    
    with open(mission_file, "w") as f:
        yaml.dump(mission_config, f)
    
    console.print(f"[green]✓ Mission {name} created in {mission_file}[/green]")


def _create_mission_from_params(name: str, objective: str, mission_type: str):
    """Create mission from parameters."""
    mission_config = {
        "name": name,
        "objective": objective or f"Complete {name}",
        "type": mission_type,
        "description": f"Mission: {objective or name}"
    }
    
    mission_file = Path("missions") / f"{name}.yaml"
    mission_file.parent.mkdir(exist_ok=True)
    
    with open(mission_file, "w") as f:
        yaml.dump(mission_config, f)
    
    console.print(f"[green]✓ Mission {name} created[/green]")


def _validate_config_structure(config_data: Dict[str, Any]) -> List[str]:
    """Validate configuration structure."""
    errors = []
    
    # Check required sections
    if "squad" not in config_data:
        errors.append("Missing 'squad' section")
    
    if "agents" not in config_data:
        errors.append("Missing 'agents' section")
    elif not isinstance(config_data["agents"], list):
        errors.append("'agents' must be a list")
    
    if "missions" not in config_data:
        errors.append("Missing 'missions' section")
    elif not isinstance(config_data["missions"], list):
        errors.append("'missions' must be a list")
    
    # Validate agent configurations
    for i, agent in enumerate(config_data.get("agents", [])):
        if "name" not in agent:
            errors.append(f"Agent {i}: missing 'name'")
        if "role" not in agent:
            errors.append(f"Agent {i}: missing 'role'")
    
    # Validate mission configurations
    for i, mission in enumerate(config_data.get("missions", [])):
        if "objective" not in mission:
            errors.append(f"Mission {i}: missing 'objective'")
    
    return errors


if __name__ == "__main__":
    app()
