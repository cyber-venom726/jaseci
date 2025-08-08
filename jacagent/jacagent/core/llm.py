"""LLM abstraction layer for JacAgent framework."""

import asyncio
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from pydantic import BaseModel, Field
from enum import Enum

from jacagent.exceptions import LLMError
from jacagent.plugins.hooks import get_hook_manager


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    CUSTOM = "custom"


class LLMMessage(BaseModel):
    """Standard message format for LLM interactions."""
    role: str = Field(description="Message role (system, user, assistant)")
    content: str = Field(description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Standard response format from LLM."""
    content: str = Field(description="Generated content")
    provider: str = Field(description="LLM provider used")
    model: str = Field(description="Model used")
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    finish_reason: Optional[str] = Field(default=None)


class LLMConfig(BaseModel):
    """Configuration for LLM calls."""
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stream: bool = Field(default=False)
    timeout: int = Field(default=30, gt=0)
    max_retries: int = Field(default=3, ge=0)
    custom_params: Dict[str, Any] = Field(default_factory=dict)


class BaseLLM(ABC):
    """Base class for LLM implementations."""
    
    def __init__(self, provider: str, config: Optional[Dict[str, Any]] = None):
        self.provider = provider
        self.config = config or {}
        self._hook_manager = get_hook_manager()
    
    @abstractmethod
    async def call(
        self, 
        messages: List[LLMMessage], 
        config: LLMConfig
    ) -> LLMResponse:
        """Make an LLM API call."""
        pass
    
    @abstractmethod
    async def stream(
        self, 
        messages: List[LLMMessage], 
        config: LLMConfig
    ) -> AsyncGenerator[str, None]:
        """Stream an LLM API call."""
        pass
    
    async def call_with_hooks(
        self, 
        messages: List[LLMMessage], 
        config: LLMConfig,
        context: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Call LLM with hook integration."""
        context = context or {}
        
        # Before hook
        hook_results = await self._hook_manager.call_hook(
            "before_llm_call",
            provider=self.provider,
            messages=[msg.dict() for msg in messages],
            config=config.dict(),
            context=context
        )
        
        # Apply hook transformations
        for result in hook_results:
            if isinstance(result, dict):
                if "messages" in result:
                    messages = [LLMMessage(**msg) for msg in result["messages"]]
                if "config" in result:
                    config = LLMConfig(**result["config"])
        
        try:
            # Make the call
            response = await self.call(messages, config)
            
            # After hook
            hook_results = await self._hook_manager.call_hook(
                "after_llm_call",
                provider=self.provider,
                response=response.dict(),
                context=context
            )
            
            # Apply hook transformations
            for result in hook_results:
                if isinstance(result, dict):
                    response = LLMResponse(**result)
                elif result is not None:
                    response.content = str(result)
            
            return response
            
        except Exception as e:
            # Error hook
            await self._hook_manager.call_hook(
                "on_llm_error",
                provider=self.provider,
                error=e,
                context=context
            )
            raise
    
    def validate_config(self, config: LLMConfig) -> None:
        """Validate LLM configuration."""
        # Override in subclasses for provider-specific validation
        pass


class OpenAILLM(BaseLLM):
    """OpenAI LLM implementation."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(LLMProvider.OPENAI, kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("OpenAI API key is required")
    
    async def call(self, messages: List[LLMMessage], config: LLMConfig) -> LLMResponse:
        """Make OpenAI API call using LiteLLM."""
        try:
            import litellm
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            response = await litellm.acompletion(
                model=config.model,
                messages=openai_messages,
                api_key=self.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
                timeout=config.timeout,
                **config.custom_params
            )
            usage = response.get("usage", {})
            choices = response.get("choices", [{}])
            finish_reason = choices[0].get("finish_reason") if choices else None
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            return LLMResponse(
                content=content,
                provider=self.provider,
                model=config.model,
                usage=usage,
                finish_reason=finish_reason
            )
        except Exception as e:
            raise LLMError(f"OpenAI API call failed: {e}")
    
    async def stream(self, messages: List[LLMMessage], config: LLMConfig) -> AsyncGenerator[str, None]:
        """Stream OpenAI API call using LiteLLM."""
        try:
            import litellm
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            async for chunk in litellm.acompletion(
                model=config.model,
                messages=openai_messages,
                api_key=self.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
                stream=True,
                timeout=config.timeout,
                **config.custom_params
            ):
                # LiteLLM yields dicts with 'choices' key, each with 'delta' or 'message'
                choices = chunk.get("choices", [{}])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
        except Exception as e:
            raise LLMError(f"OpenAI streaming failed: {e}")


class AnthropicLLM(BaseLLM):
    """Anthropic LLM implementation."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(LLMProvider.ANTHROPIC, kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise LLMError("Anthropic API key is required")
    
    async def call(self, messages: List[LLMMessage], config: LLMConfig) -> LLMResponse:
        """Make Anthropic API call using LiteLLM."""
        try:
            import litellm
            anthropic_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            response = await litellm.acompletion(
                model=config.model,
                messages=anthropic_messages,
                api_key=self.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens or 1000,
                timeout=config.timeout,
                **config.custom_params
            )
            usage = response.get("usage", {})
            choices = response.get("choices", [{}])
            finish_reason = choices[0].get("finish_reason") if choices else None
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            return LLMResponse(
                content=content,
                provider=self.provider,
                model=config.model,
                usage=usage,
                finish_reason=finish_reason
            )
        except Exception as e:
            raise LLMError(f"Anthropic API call failed: {e}")
    
    async def stream(self, messages: List[LLMMessage], config: LLMConfig) -> AsyncGenerator[str, None]:
        """Stream Anthropic API call using LiteLLM."""
        try:
            import litellm
            anthropic_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            async for chunk in litellm.acompletion(
                model=config.model,
                messages=anthropic_messages,
                api_key=self.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens or 1000,
                stream=True,
                timeout=config.timeout,
                **config.custom_params
            ):
                choices = chunk.get("choices", [{}])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
        except Exception as e:
            raise LLMError(f"Anthropic streaming failed: {e}")


class LLMFactory:
    """Factory for creating LLM instances."""
    
    _providers: Dict[str, type] = {
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.ANTHROPIC: AnthropicLLM,
    }
    
    @classmethod
    def create(cls, provider: str, **kwargs) -> BaseLLM:
        """Create an LLM instance."""
        if provider not in cls._providers:
            raise LLMError(f"Unsupported LLM provider: {provider}")
        
        llm_class = cls._providers[provider]
        return llm_class(**kwargs)
    
    @classmethod
    def register_provider(cls, provider: str, llm_class: type) -> None:
        """Register a custom LLM provider."""
        if not issubclass(llm_class, BaseLLM):
            raise LLMError("LLM class must inherit from BaseLLM")
        
        cls._providers[provider] = llm_class
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """List available LLM providers."""
        return list(cls._providers.keys())


# Convenience class for easy LLM creation
class LLMProvider:
    """Convenience class for creating LLM instances."""
    
    @staticmethod
    def openai(model: str = "gpt-4", api_key: Optional[str] = None, **kwargs) -> OpenAILLM:
        """Create OpenAI LLM instance."""
        return OpenAILLM(api_key=api_key, model=model, **kwargs)
    
    @staticmethod
    def anthropic(model: str = "claude-3-sonnet-20240229", api_key: Optional[str] = None, **kwargs) -> AnthropicLLM:
        """Create Anthropic LLM instance."""
        return AnthropicLLM(api_key=api_key, model=model, **kwargs)
    
    @staticmethod
    def custom(provider: str, **kwargs) -> BaseLLM:
        """Create custom LLM instance."""
        return LLMFactory.create(provider, **kwargs)
