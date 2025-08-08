"""Validation plugin for input/output validation and schema enforcement."""

import json
from typing import Any, Dict, Optional, List, Union, Type
from datetime import datetime
from pydantic import BaseModel, ValidationError, Field
from enum import Enum

from jacagent.plugins.base import BasePlugin
from jacagent.plugins.hooks import hookimpl
from jacagent.exceptions import ValidationError as JacValidationError


class ValidationLevel(Enum):
    """Validation strictness levels."""
    STRICT = "strict"          # Fail on any validation error
    WARN = "warn"              # Log warnings but continue
    PERMISSIVE = "permissive"  # Only validate critical fields


class PromptValidationSchema(BaseModel):
    """Schema for prompt validation."""
    min_length: int = Field(default=1, ge=0)
    max_length: int = Field(default=10000, ge=1)
    required_keywords: List[str] = Field(default_factory=list)
    forbidden_patterns: List[str] = Field(default_factory=list)
    language_code: Optional[str] = None


class ResponseValidationSchema(BaseModel):
    """Schema for response validation."""
    min_length: int = Field(default=1, ge=0)
    max_length: int = Field(default=50000, ge=1)
    required_format: Optional[str] = None  # json, markdown, plain
    required_fields: List[str] = Field(default_factory=list)
    schema_validation: Optional[Dict[str, Any]] = None


class MissionValidationSchema(BaseModel):
    """Schema for mission validation."""
    objective_min_length: int = Field(default=10, ge=1)
    objective_max_length: int = Field(default=1000, ge=1)
    required_mission_fields: List[str] = Field(default_factory=lambda: ["objective"])
    allowed_mission_types: List[str] = Field(default_factory=list)
    max_steps: int = Field(default=50, ge=1)


class AgentValidationSchema(BaseModel):
    """Schema for agent validation."""
    name_pattern: str = Field(default=r"^[a-zA-Z0-9_-]+$")
    required_capabilities: List[str] = Field(default_factory=list)
    max_capabilities: int = Field(default=20, ge=1)
    role_whitelist: List[str] = Field(default_factory=list)


class ValidationPlugin(BasePlugin):
    """Plugin for comprehensive input/output validation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        
        # Validation level
        self.validation_level = ValidationLevel(
            self.config.get("validation_level", "warn")
        )
        
        # Validation schemas
        self.prompt_schema = PromptValidationSchema(
            **self.config.get("prompt_validation", {})
        )
        self.response_schema = ResponseValidationSchema(
            **self.config.get("response_validation", {})
        )
        self.mission_schema = MissionValidationSchema(
            **self.config.get("mission_validation", {})
        )
        self.agent_schema = AgentValidationSchema(
            **self.config.get("agent_validation", {})
        )
        
        # Custom validators
        self.custom_validators: Dict[str, callable] = {}
        
        # Validation statistics
        self.validation_stats = {
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "warning_validations": 0,
            "validation_errors": []
        }
    
    def get_name(self) -> str:
        return "validation"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Input/output validation and schema enforcement"
    
    def register_custom_validator(self, name: str, validator: callable):
        """Register a custom validator function."""
        self.custom_validators[name] = validator
    
    def _handle_validation_error(self, error_msg: str, context: Dict[str, Any]):
        """Handle validation error based on validation level."""
        self.validation_stats["total_validations"] += 1
        
        validation_error = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_msg,
            "context": context,
            "level": self.validation_level.value
        }
        
        if self.validation_level == ValidationLevel.STRICT:
            self.validation_stats["failed_validations"] += 1
            self.validation_stats["validation_errors"].append(validation_error)
            raise JacValidationError(error_msg)
        elif self.validation_level == ValidationLevel.WARN:
            self.validation_stats["warning_validations"] += 1
            self.validation_stats["validation_errors"].append(validation_error)
            print(f"Validation Warning: {error_msg}")
        else:  # PERMISSIVE
            self.validation_stats["warning_validations"] += 1
    
    def _validate_prompt(self, prompt: str, context: Dict[str, Any]) -> bool:
        """Validate prompt content."""
        errors = []
        
        # Length validation
        if len(prompt) < self.prompt_schema.min_length:
            errors.append(f"Prompt too short: {len(prompt)} < {self.prompt_schema.min_length}")
        
        if len(prompt) > self.prompt_schema.max_length:
            errors.append(f"Prompt too long: {len(prompt)} > {self.prompt_schema.max_length}")
        
        # Required keywords
        for keyword in self.prompt_schema.required_keywords:
            if keyword.lower() not in prompt.lower():
                errors.append(f"Missing required keyword: {keyword}")
        
        # Forbidden patterns
        import re
        for pattern in self.prompt_schema.forbidden_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                errors.append(f"Contains forbidden pattern: {pattern}")
        
        # Language validation (if specified)
        if self.prompt_schema.language_code:
            # This would integrate with language detection library
            pass
        
        if errors:
            self._handle_validation_error(
                f"Prompt validation failed: {'; '.join(errors)}",
                {"prompt_length": len(prompt), **context}
            )
            return False
        
        self.validation_stats["total_validations"] += 1
        self.validation_stats["passed_validations"] += 1
        return True
    
    def _validate_response(self, response: str, context: Dict[str, Any]) -> bool:
        """Validate response content."""
        errors = []
        
        # Length validation
        if len(response) < self.response_schema.min_length:
            errors.append(f"Response too short: {len(response)} < {self.response_schema.min_length}")
        
        if len(response) > self.response_schema.max_length:
            errors.append(f"Response too long: {len(response)} > {self.response_schema.max_length}")
        
        # Format validation
        if self.response_schema.required_format:
            if not self._validate_format(response, self.response_schema.required_format):
                errors.append(f"Invalid format: expected {self.response_schema.required_format}")
        
        # Schema validation for structured responses
        if self.response_schema.schema_validation:
            if not self._validate_json_schema(response, self.response_schema.schema_validation):
                errors.append("Response does not match required schema")
        
        # Required fields validation
        if self.response_schema.required_fields:
            if not self._validate_required_fields(response, self.response_schema.required_fields):
                errors.append("Missing required fields in response")
        
        if errors:
            self._handle_validation_error(
                f"Response validation failed: {'; '.join(errors)}",
                {"response_length": len(response), **context}
            )
            return False
        
        self.validation_stats["total_validations"] += 1
        self.validation_stats["passed_validations"] += 1
        return True
    
    def _validate_format(self, content: str, format_type: str) -> bool:
        """Validate content format."""
        if format_type == "json":
            try:
                json.loads(content)
                return True
            except json.JSONDecodeError:
                return False
        elif format_type == "markdown":
            # Basic markdown validation
            return any(marker in content for marker in ["#", "*", "**", "`", "```"])
        elif format_type == "plain":
            # Plain text - always valid
            return True
        
        return True
    
    def _validate_json_schema(self, content: str, schema: Dict[str, Any]) -> bool:
        """Validate JSON content against schema."""
        try:
            data = json.loads(content)
            # This would integrate with jsonschema library for full validation
            # For now, basic validation
            return isinstance(data, dict)
        except (json.JSONDecodeError, TypeError):
            return False
    
    def _validate_required_fields(self, content: str, required_fields: List[str]) -> bool:
        """Validate that required fields are present."""
        try:
            if content.startswith("{"):  # JSON format
                data = json.loads(content)
                return all(field in data for field in required_fields)
            else:  # Text format - check for field mentions
                return all(field.lower() in content.lower() for field in required_fields)
        except json.JSONDecodeError:
            # Fallback to text search
            return all(field.lower() in content.lower() for field in required_fields)
    
    def _validate_mission(self, mission, context: Dict[str, Any]) -> bool:
        """Validate mission configuration."""
        errors = []
        
        # Objective validation
        if hasattr(mission, 'objective'):
            obj_len = len(mission.objective)
            if obj_len < self.mission_schema.objective_min_length:
                errors.append(f"Mission objective too short: {obj_len}")
            if obj_len > self.mission_schema.objective_max_length:
                errors.append(f"Mission objective too long: {obj_len}")
        
        # Required fields
        for field in self.mission_schema.required_mission_fields:
            if not hasattr(mission, field) or not getattr(mission, field):
                errors.append(f"Missing required mission field: {field}")
        
        # Mission type validation
        if (self.mission_schema.allowed_mission_types and 
            hasattr(mission, 'mission_type') and 
            mission.mission_type.value not in self.mission_schema.allowed_mission_types):
            errors.append(f"Invalid mission type: {mission.mission_type.value}")
        
        # Steps validation
        if hasattr(mission, 'steps') and len(mission.steps) > self.mission_schema.max_steps:
            errors.append(f"Too many mission steps: {len(mission.steps)} > {self.mission_schema.max_steps}")
        
        if errors:
            self._handle_validation_error(
                f"Mission validation failed: {'; '.join(errors)}",
                {"mission_id": getattr(mission, 'id', 'unknown'), **context}
            )
            return False
        
        self.validation_stats["total_validations"] += 1
        self.validation_stats["passed_validations"] += 1
        return True
    
    def _validate_agent(self, agent, context: Dict[str, Any]) -> bool:
        """Validate agent configuration."""
        errors = []
        
        # Name validation
        import re
        if not re.match(self.agent_schema.name_pattern, agent.name):
            errors.append(f"Invalid agent name pattern: {agent.name}")
        
        # Capabilities validation
        if hasattr(agent, 'config') and hasattr(agent.config, 'capabilities'):
            capabilities = agent.config.capabilities
            
            if len(capabilities) > self.agent_schema.max_capabilities:
                errors.append(f"Too many capabilities: {len(capabilities)} > {self.agent_schema.max_capabilities}")
            
            for required_cap in self.agent_schema.required_capabilities:
                if required_cap not in capabilities:
                    errors.append(f"Missing required capability: {required_cap}")
        
        # Role validation
        if (self.agent_schema.role_whitelist and 
            agent.role not in self.agent_schema.role_whitelist):
            errors.append(f"Invalid agent role: {agent.role}")
        
        if errors:
            self._handle_validation_error(
                f"Agent validation failed: {'; '.join(errors)}",
                {"agent_id": agent.id, "agent_name": agent.name, **context}
            )
            return False
        
        self.validation_stats["total_validations"] += 1
        self.validation_stats["passed_validations"] += 1
        return True
    
    @hookimpl
    def llm_request_started(self, agent, prompt, context):
        """Validate LLM request prompt."""
        self._validate_prompt(prompt, {"agent_id": agent.id, "context": context})
    
    @hookimpl
    def llm_response_received(self, agent, prompt, response, metrics):
        """Validate LLM response."""
        if response:
            self._validate_response(response, {"agent_id": agent.id, "prompt_length": len(prompt)})
    
    @hookimpl
    def mission_created(self, mission):
        """Validate mission when created."""
        self._validate_mission(mission, {"creation_time": datetime.utcnow().isoformat()})
    
    @hookimpl
    def agent_created(self, agent):
        """Validate agent when created."""
        self._validate_agent(agent, {"creation_time": datetime.utcnow().isoformat()})
    
    @hookimpl
    def tool_execution_started(self, agent, tool_name, parameters):
        """Validate tool parameters."""
        if parameters:
            # Run custom validators if available
            validator_name = f"tool_{tool_name}"
            if validator_name in self.custom_validators:
                try:
                    self.custom_validators[validator_name](parameters)
                    self.validation_stats["total_validations"] += 1
                    self.validation_stats["passed_validations"] += 1
                except Exception as e:
                    self._handle_validation_error(
                        f"Tool parameter validation failed: {e}",
                        {"agent_id": agent.id, "tool_name": tool_name}
                    )
    
    def validate_custom(self, data: Any, validator_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Run custom validation."""
        if validator_name not in self.custom_validators:
            self._handle_validation_error(
                f"Unknown validator: {validator_name}",
                context or {}
            )
            return False
        
        try:
            self.custom_validators[validator_name](data)
            self.validation_stats["total_validations"] += 1
            self.validation_stats["passed_validations"] += 1
            return True
        except Exception as e:
            self._handle_validation_error(
                f"Custom validation failed: {e}",
                {"validator": validator_name, **(context or {})}
            )
            return False
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total = self.validation_stats["total_validations"]
        return {
            "total_validations": total,
            "passed_validations": self.validation_stats["passed_validations"],
            "failed_validations": self.validation_stats["failed_validations"],
            "warning_validations": self.validation_stats["warning_validations"],
            "success_rate": (
                self.validation_stats["passed_validations"] / total 
                if total > 0 else 0.0
            ),
            "validation_level": self.validation_level.value,
            "recent_errors": self.validation_stats["validation_errors"][-10:],  # Last 10 errors
            "error_count": len(self.validation_stats["validation_errors"])
        }
    
    def update_validation_level(self, level: ValidationLevel):
        """Update validation strictness level."""
        self.validation_level = level
    
    def clear_validation_history(self):
        """Clear validation statistics and error history."""
        self.validation_stats = {
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "warning_validations": 0,
            "validation_errors": []
        }
