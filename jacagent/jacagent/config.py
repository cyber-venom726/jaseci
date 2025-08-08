"""Configuration management for JacAgent framework."""

import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field, validator
from enum import Enum


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MemoryBackend(str, Enum):
    """Memory backend types."""
    LOCAL = "local"
    REDIS = "redis"
    POSTGRES = "postgres"
    CHROMA = "chroma"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"


class SecurityConfig(BaseModel):
    """Security configuration."""
    enable_input_validation: bool = Field(default=True)
    enable_output_filtering: bool = Field(default=True)
    enable_audit_logging: bool = Field(default=True)
    max_execution_time: Optional[int] = Field(default=300)
    rate_limit_per_minute: Optional[int] = Field(default=60)
    allowed_domains: List[str] = Field(default_factory=list)
    blocked_patterns: List[str] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    """Memory configuration."""
    backend: MemoryBackend = Field(default=MemoryBackend.LOCAL)
    connection_string: Optional[str] = Field(default=None)
    vector_dimension: int = Field(default=1536)
    max_memory_size: int = Field(default=1000)  # MB
    cleanup_interval: int = Field(default=3600)  # seconds
    enable_compression: bool = Field(default=True)
    
    @validator('connection_string')
    def validate_connection_string(cls, v, values):
        backend = values.get('backend')
        if backend != MemoryBackend.LOCAL and not v:
            raise ValueError(f"Connection string required for {backend} backend")
        return v


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=True)
    metrics_port: int = Field(default=9090)
    jaeger_endpoint: Optional[str] = Field(default=None)
    prometheus_endpoint: Optional[str] = Field(default="/metrics")
    log_level: LogLevel = Field(default=LogLevel.INFO)
    export_interval: int = Field(default=60)  # seconds


class LLMConfig(BaseModel):
    """LLM configuration."""
    default_provider: str = Field(default="openai")
    api_keys: Dict[str, str] = Field(default_factory=dict)
    model_mappings: Dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=30)
    max_retries: int = Field(default=3)
    rate_limits: Dict[str, int] = Field(default_factory=dict)
    cache_responses: bool = Field(default=True)
    cache_ttl: int = Field(default=3600)  # seconds


class PluginConfig(BaseModel):
    """Plugin configuration."""
    enabled_plugins: List[str] = Field(default_factory=list)
    plugin_directories: List[str] = Field(default_factory=list)
    auto_discover: bool = Field(default=True)
    allow_external: bool = Field(default=False)
    sandbox_mode: bool = Field(default=True)


class WebUIConfig(BaseModel):
    """Web UI configuration."""
    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8080)
    auth_enabled: bool = Field(default=False)
    auth_secret: Optional[str] = Field(default=None)
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])


class JacAgentConfig(BaseModel):
    """Main configuration for JacAgent framework."""
    
    # Core settings
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    data_directory: Path = Field(default=Path.home() / ".jacagent")
    temp_directory: Path = Field(default=Path.home() / ".jacagent" / "temp")
    
    # Component configurations
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    webui: WebUIConfig = Field(default_factory=WebUIConfig)
    
    # Advanced settings
    max_concurrent_agents: int = Field(default=10)
    max_concurrent_missions: int = Field(default=5)
    default_timeout: int = Field(default=300)
    enable_telemetry: bool = Field(default=True)
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "JACAGENT_"
        case_sensitive = False
        
    @validator('data_directory', 'temp_directory')
    def ensure_directory_exists(cls, v):
        """Ensure directories exist."""
        v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "JacAgentConfig":
        """Load configuration from file."""
        import json
        import yaml
        
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif config_path.suffix.lower() == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {config_path.suffix}")
        
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "JacAgentConfig":
        """Load configuration from environment variables."""
        return cls()
    
    def to_file(self, config_path: Union[str, Path], format: str = "yaml") -> None:
        """Save configuration to file."""
        import json
        import yaml
        
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.dict()
        
        with open(config_path, 'w') as f:
            if format.lower() in ['yaml', 'yml']:
                yaml.safe_dump(data, f, default_flow_style=False)
            elif format.lower() == 'json':
                json.dump(data, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")


# Global configuration instance
_global_config: Optional[JacAgentConfig] = None


def get_config() -> JacAgentConfig:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = JacAgentConfig.from_env()
    return _global_config


def set_config(config: JacAgentConfig) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset the global configuration to default."""
    global _global_config
    _global_config = None
