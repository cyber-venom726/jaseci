"""Jac Type Model Package.

This package contains the core type system components for the Jac language,
inspired by Microsoft's Pyright architecture. It provides:

- Type hierarchy with rich type representations
- Type caching for performance optimization
- Type evaluation and analysis engines
- Flow analysis for type narrowing
- Symbol resolution and type inference

The architecture follows Pyright's proven patterns while being tailored
for Jac's unique features like archetypes, walkers, and abilities.
"""

from .types import (
    JacType,
    UnknownType,
    AnyType,
    NoneType,
    BuiltinType,
    ArchetypeType,
    WalkerType,
    EdgeType,
    NodeType,
    CallableType,
    UnionType,
    GenericType,
    TypeVar,
    TupleType,
    ListType,
    DictType,
    LiteralType,
    # Export common type instances
    UNKNOWN_TYPE,
    ANY_TYPE,
    NONE_TYPE,
    INT_TYPE,
    FLOAT_TYPE,
    STR_TYPE,
    BOOL_TYPE,
)

from .type_factory import TypeFactory
from .type_cache import TypeCache
from .type_evaluator import TypeEvaluator, TypeEvaluationContext
from .flow_analyzer import FlowAnalyzer

__all__ = [
    "JacType",
    "UnknownType", 
    "AnyType",
    "NoneType",
    "BuiltinType",
    "ArchetypeType",
    "WalkerType",
    "EdgeType", 
    "NodeType",
    "CallableType",
    "UnionType",
    "GenericType",
    "TypeVar",
    "TupleType",
    "ListType",
    "DictType",
    "LiteralType",
    "TypeFactory",
    "TypeCache", 
    "TypeEvaluator",
    "TypeEvaluationContext",
    "FlowAnalyzer",
    # Common type instances
    "UNKNOWN_TYPE",
    "ANY_TYPE", 
    "NONE_TYPE",
    "INT_TYPE",
    "FLOAT_TYPE",
    "STR_TYPE",
    "BOOL_TYPE",
]
