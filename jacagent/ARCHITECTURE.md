# JacAgent Architecture & Flow

## Overview
JacAgent is a modular, extensible framework for interacting with Large Language Models (LLMs) and orchestrating agent-based workflows. It provides abstractions for LLM providers, message handling, plugin hooks, and orchestration patterns, making it easy to build, extend, and customize AI-powered agents.

---

## High-Level Architecture

```
+-------------------+
|  User/CLI/API     |
+-------------------+
          |
          v
+-------------------+
|   Orchestration   |  <-- Patterns, Missions, Squads
+-------------------+
          |
          v
+-------------------+
|      Core         |  <-- Agent, LLM, Memory, Tools
+-------------------+
          |
          v
+-------------------+
|    Plugins        |  <-- Hooks, Logging, Metrics, etc.
+-------------------+
```

- **User/CLI/API**: Entry points for interacting with JacAgent (e.g., CLI commands, API calls).
- **Orchestration**: Defines high-level patterns, missions, and squads for agent workflows.
- **Core**: Implements the main agent logic, LLM abstraction, memory, and tool interfaces.
- **Plugins**: Extensible hooks for logging, metrics, validation, retries, and custom behaviors.

---

## Core Components & Flow

### 1. LLM Abstraction (`jacagent/core/llm.py`)
- **LLMProvider Enum**: Lists supported LLM providers (OpenAI, Anthropic, etc.).
- **LLMMessage/LLMResponse**: Standardizes message and response formats.
- **LLMConfig**: Configuration for LLM calls (model, temperature, etc.).
- **BaseLLM**: Abstract base for all LLM implementations.
- **OpenAILLM/AnthropicLLM**: Provider-specific implementations (now using LiteLLM for unified API calls).
- **LLMFactory**: Factory for creating LLM instances by provider.
- **Hooks**: Before/after/error hooks for LLM calls (plugin system).

### 2. Agent & Memory (`jacagent/core/agent.py`, `memory.py`)
- **Agent**: Encapsulates agent state, LLM, memory, and tool usage.
- **Memory**: Stores conversation history and context.

### 3. Tools (`jacagent/core/tools.py`)
- **Tools**: Extensible interface for agent tools (e.g., search, calculator, web access).

### 4. Orchestration (`jacagent/orchestration/patterns.py`, `mission.py`, `squad.py`)
- **Patterns**: Defines reusable orchestration patterns for agent workflows.
- **Mission**: Encapsulates a single agent task or goal.
- **Squad**: Manages multiple agents working together.

### 5. Plugins (`jacagent/plugins/`)
- **Hooks**: Plugin system for before/after/error hooks on LLM calls and agent actions.
- **Built-in Plugins**: Logging, metrics, retry, validation, etc.
- **Custom Plugins**: Users can register their own plugins for custom behaviors.

---


## Typical Flow

### Step-by-Step Flow

1. **User Input**: User interacts with JacAgent via CLI, API, or another interface.
2. **Orchestration Layer**: The input is routed through orchestration patterns (e.g., a mission or squad), which determine the agent(s) and workflow to use.
3. **Agent Logic**: The agent receives the input, updates memory, and determines whether to use tools, call an LLM, or take other actions.
4. **LLM Call Initiation**: The agent constructs a list of `LLMMessage` objects and an `LLMConfig` for the LLM call.
5. **Hooks - Before Call**: The `call_with_hooks()` method triggers `before_llm_call` hooks, allowing plugins to modify the messages or config.
6. **LLM Provider Call**: The LLM abstraction (using LiteLLM) sends the request to the selected LLM provider (e.g., OpenAI, Anthropic).
7. **Hooks - After/Error**: After the LLM responds, `after_llm_call` hooks are triggered. If an error occurs, `on_llm_error` hooks are triggered.
8. **Response Handling**: The agent receives the LLM response, updates memory, and determines the next action or returns output to the user.

### Flow Diagram

```
User/CLI/API
    |
    v
Orchestration Layer (patterns, missions, squads)
    |
    v
Agent (memory, tools, logic)
    |
    v
Hooks: before_llm_call
    |
    v
LLM Abstraction (BaseLLM, LiteLLM)
    |
    v
LLM Provider (OpenAI, Anthropic, etc.)
    |
    v
Hooks: after_llm_call / on_llm_error
    |
    v
Agent (memory update, next action)
    |
    v
User Output
```

This flow ensures extensibility at each stage, allowing plugins and custom logic to be injected before and after LLM calls, and enabling complex agent orchestration patterns.

---

## Extensibility
- **Add new LLM providers**: Implement a new subclass of `BaseLLM` and register it with `LLMFactory`.
- **Add plugins**: Create a plugin and register it in the hooks system.
- **Add tools**: Implement new tools in `core/tools.py` and register with the agent.
- **Customize orchestration**: Define new patterns, missions, or squads in the orchestration layer.

---

## Dependencies
- **LiteLLM**: Unified async API for multiple LLM providers.
- **Pydantic**: Data validation and settings management.

---

## Example: LLM Call Flow

1. Agent receives user message.
2. Agent constructs `LLMMessage` list and `LLMConfig`.
3. Calls `BaseLLM.call_with_hooks()`:
    - Triggers `before_llm_call` hooks (plugins can modify messages/config).
    - Calls provider via LiteLLM.
    - Triggers `after_llm_call` hooks (plugins can modify/observe response).
    - On error, triggers `on_llm_error` hooks.
4. Agent processes response and returns to user.

---

## File Structure Reference
- `jacagent/core/llm.py` - LLM abstraction and providers
- `jacagent/core/agent.py` - Agent logic
- `jacagent/core/memory.py` - Memory management
- `jacagent/core/tools.py` - Tool interface
- `jacagent/orchestration/` - Patterns, missions, squads
- `jacagent/plugins/` - Plugin system and built-in plugins

---

## Summary
JacAgent is designed for flexibility, extensibility, and ease of integration with multiple LLM providers and agent workflows. Its architecture separates concerns between orchestration, agent logic, LLM abstraction, and plugins, making it easy to extend and customize for advanced AI agent applications.
