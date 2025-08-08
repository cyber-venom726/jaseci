"""Core type representations for the Jac type system.

This module implements the type hierarchy inspired by Pyright's architecture,
providing rich type representations with caching and efficient comparison.
All types are immutable and hashable for use as dictionary keys.
"""

from __future__ import annotations

import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
    Type as PyType,
    TypeVar as PyTypeVar,
    Union,
    cast,
)

import jaclang.compiler.unitree as uni
from jaclang.compiler.unitree import Symbol


# Type variable for generic type operations
T = PyTypeVar("T", bound="JacType")


class JacTypeFlags:
    """Flags for type characteristics."""
    
    NONE = 0
    INSTANTIABLE = 1 << 0
    GENERIC = 1 << 1  
    SPECIAL_FORM = 1 << 2
    CLASS = 1 << 3
    CALLABLE = 1 << 4
    ARCHETYPE = 1 << 5
    WALKER = 1 << 6
    EDGE = 1 << 7
    NODE = 1 << 8


@dataclass(frozen=True)
class TypeSource:
    """Source information for a type (where it was declared)."""
    
    module_name: str
    location: Optional[uni.CodeLocInfo] = None
    declaration: Optional[uni.UniNode] = None


class JacType(ABC):
    """Base class for all types in the Jac type system.
    
    All types are immutable and hashable for efficient caching.
    Follows Pyright's pattern of object-based type representation.
    """
    
    def __init__(
        self,
        *,
        display_name: str = "",
        type_source: Optional[TypeSource] = None,
        flags: int = JacTypeFlags.NONE,
    ) -> None:
        self._display_name = display_name
        self._type_source = type_source  
        self._flags = flags
        self._hash: Optional[int] = None
        
    def _init_base_fields(
        self,
        *,
        display_name: str = "",
        type_source: Optional[TypeSource] = None,
        flags: int = JacTypeFlags.NONE,
    ) -> None:
        """Initialize base fields for dataclass subclasses."""
        object.__setattr__(self, '_display_name', display_name)
        object.__setattr__(self, '_type_source', type_source)
        object.__setattr__(self, '_flags', flags)
        object.__setattr__(self, '_hash', None)
        
    @property
    def display_name(self) -> str:
        """Human-readable name for this type."""
        return self._display_name or self._get_default_display_name()
        
    @property
    def type_source(self) -> Optional[TypeSource]:
        """Source information for this type."""
        return self._type_source
        
    @property
    def flags(self) -> int:
        """Type characteristic flags."""
        return self._flags
        
    @abstractmethod
    def _get_default_display_name(self) -> str:
        """Get the default display name for this type."""
        ...
        
    @abstractmethod
    def is_compatible_with(self, other: JacType) -> bool:
        """Check if this type is compatible with another type."""
        ...
        
    def is_assignable_to(self, target: JacType) -> bool:
        """Check if this type can be assigned to the target type."""
        return target.is_compatible_with(self)
        
    def has_flag(self, flag: int) -> bool:
        """Check if this type has a specific flag."""
        return (self._flags & flag) != 0
        
    def is_instantiable(self) -> bool:
        """Check if this type can be instantiated."""
        return self.has_flag(JacTypeFlags.INSTANTIABLE)
        
    def is_generic(self) -> bool:
        """Check if this type is generic."""
        return self.has_flag(JacTypeFlags.GENERIC)
        
    def is_callable(self) -> bool:
        """Check if this type is callable."""
        return self.has_flag(JacTypeFlags.CALLABLE)
        
    def __hash__(self) -> int:
        """Hash for efficient dictionary lookups and caching."""
        if self._hash is None:
            self._hash = self._compute_hash()
        return self._hash
        
    @abstractmethod
    def _compute_hash(self) -> int:
        """Compute hash value for this type."""
        ...
        
    def __eq__(self, other: object) -> bool:
        """Equality comparison for types."""
        if not isinstance(other, JacType):
            return False
        return hash(self) == hash(other) and self._is_equal_to(other)
        
    @abstractmethod
    def _is_equal_to(self, other: JacType) -> bool:
        """Internal equality check."""
        ...
        
    def __str__(self) -> str:
        """String representation."""
        return self.display_name
        
    def __repr__(self) -> str:
        """Debug representation."""
        return f"{self.__class__.__name__}({self.display_name})"


class UnknownType(JacType):
    """Type representing unknown/unresolved types."""
    
    _instance: Optional[UnknownType] = None
    
    def __new__(cls) -> UnknownType:
        """Singleton pattern for Unknown type."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(display_name="Unknown")
        self._initialized = True
        
    def _get_default_display_name(self) -> str:
        return "Unknown"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Unknown is compatible with any type."""
        return True
        
    def _compute_hash(self) -> int:
        return hash("Unknown")
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, UnknownType)


class AnyType(JacType):
    """Type representing the 'any' type (disables type checking)."""
    
    _instance: Optional[AnyType] = None
    
    def __new__(cls) -> AnyType:
        """Singleton pattern for Any type."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(display_name="any")
        self._initialized = True
        
    def _get_default_display_name(self) -> str:
        return "any"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Any is compatible with any type."""
        return True
        
    def _compute_hash(self) -> int:
        return hash("any")
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, AnyType)


class NoneType(JacType):
    """Type representing None/null values."""
    
    _instance: Optional[NoneType] = None
    
    def __new__(cls) -> NoneType:
        """Singleton pattern for None type."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(display_name="None")
        self._initialized = True
        
    def _get_default_display_name(self) -> str:
        return "None"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """None is only compatible with None and nullable types."""
        return isinstance(other, (NoneType, UnionType)) or \
               (isinstance(other, UnionType) and any(isinstance(t, NoneType) for t in other.types))
        
    def _compute_hash(self) -> int:
        return hash("None")
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, NoneType)


@dataclass(frozen=True)
class BuiltinType(JacType):
    """Type representing built-in primitive types."""
    
    name: str
    python_type: Optional[PyType[Any]] = None
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self.name,
            flags=JacTypeFlags.INSTANTIABLE
        )
        
    def _get_default_display_name(self) -> str:
        return self.name
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Built-in types are compatible with same type."""
        return isinstance(other, BuiltinType) and self.name == other.name
        
    def _compute_hash(self) -> int:
        return hash(("builtin", self.name))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, BuiltinType) and self.name == other.name
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, BuiltinType) and self.name == other.name


@dataclass(frozen=True)
class ArchetypeType(JacType):
    """Type representing Jac archetypes (classes)."""
    
    name: str
    symbol: Optional[Symbol] = None
    base_types: Tuple[JacType, ...] = field(default_factory=tuple)
    type_parameters: Tuple[TypeVar, ...] = field(default_factory=tuple)
    members: Optional[Dict[str, JacType]] = None
    
    def __post_init__(self) -> None:
        flags = JacTypeFlags.INSTANTIABLE | JacTypeFlags.ARCHETYPE | JacTypeFlags.CLASS
        if self.type_parameters:
            flags |= JacTypeFlags.GENERIC
        self._init_base_fields(
            display_name=self.name,
            flags=flags
        )
        
    def _get_default_display_name(self) -> str:
        if self.type_parameters:
            params = ", ".join(tp.name for tp in self.type_parameters)
            return f"{self.name}[{params}]"
        return self.name
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Archetype compatibility based on inheritance."""
        if isinstance(other, ArchetypeType):
            if self.name == other.name:
                return True
            # Check inheritance hierarchy
            return any(base.is_compatible_with(other) for base in self.base_types)
        return False
        
    def _compute_hash(self) -> int:
        return hash(("archetype", self.name, self.type_parameters))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, ArchetypeType) and 
                self.name == other.name and 
                self.type_parameters == other.type_parameters)
                
    def get_member_type(self, name: str) -> Optional[JacType]:
        """Get the type of a member by name."""
        if self.members:
            return self.members.get(name)
        # TODO: Look up in symbol table
        return None


@dataclass(frozen=True)
class WalkerType(JacType):
    """Type representing Jac walkers."""
    
    name: str
    symbol: Optional[Symbol] = None
    abilities: Tuple[CallableType, ...] = field(default_factory=tuple)
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self.name,
            flags=JacTypeFlags.INSTANTIABLE | JacTypeFlags.WALKER | JacTypeFlags.CLASS
        )
        
    def _get_default_display_name(self) -> str:
        return self.name
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Walker compatibility."""
        return isinstance(other, WalkerType) and self.name == other.name
        
    def _compute_hash(self) -> int:
        return hash(("walker", self.name))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, WalkerType) and self.name == other.name


@dataclass(frozen=True)
class EdgeType(JacType):
    """Type representing Jac edges."""
    
    name: str
    symbol: Optional[Symbol] = None
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self.name,
            flags=JacTypeFlags.INSTANTIABLE | JacTypeFlags.EDGE | JacTypeFlags.CLASS
        )
        
    def _get_default_display_name(self) -> str:
        return self.name
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Edge compatibility."""
        return isinstance(other, EdgeType) and self.name == other.name
        
    def _compute_hash(self) -> int:
        return hash(("edge", self.name))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, EdgeType) and self.name == other.name


@dataclass(frozen=True)
class NodeType(JacType):
    """Type representing Jac nodes."""
    
    name: str
    symbol: Optional[Symbol] = None
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self.name,
            flags=JacTypeFlags.INSTANTIABLE | JacTypeFlags.NODE | JacTypeFlags.CLASS
        )
        
    def _get_default_display_name(self) -> str:
        return self.name
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Node compatibility."""
        return isinstance(other, NodeType) and self.name == other.name
        
    def _compute_hash(self) -> int:
        return hash(("node", self.name))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, NodeType) and self.name == other.name


@dataclass(frozen=True)
class CallableType(JacType):
    """Type representing callable entities (functions, methods, abilities)."""
    
    name: str
    parameters: Tuple[JacType, ...] = field(default_factory=tuple)
    return_type: Optional[JacType] = None
    is_method: bool = False
    is_ability: bool = False
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self.name,
            flags=JacTypeFlags.CALLABLE
        )
        
    def _get_default_display_name(self) -> str:
        param_str = ", ".join(str(p) for p in self.parameters)
        ret_str = f" -> {self.return_type}" if self.return_type else ""
        return f"{self.name}({param_str}){ret_str}"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Callable compatibility based on signature."""
        if not isinstance(other, CallableType):
            return False
        
        # Check parameter compatibility
        if len(self.parameters) != len(other.parameters):
            return False
            
        for p1, p2 in zip(self.parameters, other.parameters):
            if not p1.is_compatible_with(p2):
                return False
                
        # Check return type compatibility
        if self.return_type and other.return_type:
            return self.return_type.is_compatible_with(other.return_type)
            
        return True
        
    def _compute_hash(self) -> int:
        return hash(("callable", self.name, self.parameters, self.return_type))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, CallableType) and
                self.name == other.name and
                self.parameters == other.parameters and
                self.return_type == other.return_type)


@dataclass(frozen=True)
class UnionType(JacType):
    """Type representing union of multiple types."""
    
    types: FrozenSet[JacType]
    
    def __post_init__(self) -> None:
        # Flatten nested unions and remove duplicates
        flattened = set()
        for t in self.types:
            if isinstance(t, UnionType):
                flattened.update(t.types)
            else:
                flattened.add(t)
        object.__setattr__(self, 'types', frozenset(flattened))
        
        self._init_base_fields(
            display_name=self._create_display_name()
        )
        
    def _create_display_name(self) -> str:
        """Create display name for union type."""
        sorted_types = sorted(self.types, key=lambda t: t.display_name)
        return " | ".join(t.display_name for t in sorted_types)
        
    def _get_default_display_name(self) -> str:
        return self._create_display_name()
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Union is compatible if any member type is compatible."""
        if isinstance(other, UnionType):
            # All types in self must be compatible with some type in other
            return all(any(t1.is_compatible_with(t2) for t2 in other.types) 
                      for t1 in self.types)
        else:
            # Any type in union must be compatible with other
            return any(t.is_compatible_with(other) for t in self.types)
            
    def _compute_hash(self) -> int:
        return hash(("union", self.types))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, UnionType) and self.types == other.types
        
    def contains_type(self, type_to_check: JacType) -> bool:
        """Check if union contains a specific type."""
        return type_to_check in self.types or \
               any(t.is_compatible_with(type_to_check) for t in self.types)


@dataclass(frozen=True)
class GenericType(JacType):
    """Type representing generic types with type parameters."""
    
    base_type: JacType
    type_arguments: Tuple[JacType, ...] = field(default_factory=tuple)
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self._create_display_name(),
            flags=JacTypeFlags.GENERIC | self.base_type.flags
        )
        
    def _create_display_name(self) -> str:
        """Create display name for generic type."""
        if self.type_arguments:
            args = ", ".join(arg.display_name for arg in self.type_arguments)
            return f"{self.base_type.display_name}[{args}]"
        return self.base_type.display_name
        
    def _get_default_display_name(self) -> str:
        return self._create_display_name()
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Generic type compatibility."""
        if isinstance(other, GenericType):
            return (self.base_type.is_compatible_with(other.base_type) and
                   len(self.type_arguments) == len(other.type_arguments) and
                   all(a1.is_compatible_with(a2) for a1, a2 in 
                       zip(self.type_arguments, other.type_arguments)))
        return self.base_type.is_compatible_with(other)
        
    def _compute_hash(self) -> int:
        return hash(("generic", self.base_type, self.type_arguments))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, GenericType) and
                self.base_type == other.base_type and
                self.type_arguments == other.type_arguments)


@dataclass(frozen=True)
class TypeVar(JacType):
    """Type representing type variables in generic contexts."""
    
    name: str
    bound: Optional[JacType] = None
    constraints: Tuple[JacType, ...] = field(default_factory=tuple)
    
    def __post_init__(self) -> None:
        self._init_base_fields(display_name=self.name)
        
    def _get_default_display_name(self) -> str:
        return self.name
        
    def is_compatible_with(self, other: JacType) -> bool:
        """TypeVar compatibility based on bounds and constraints."""
        if isinstance(other, TypeVar):
            return self.name == other.name
            
        # Check against bound
        if self.bound:
            return other.is_assignable_to(self.bound)
            
        # Check against constraints
        if self.constraints:
            return any(other.is_assignable_to(constraint) 
                      for constraint in self.constraints)
                      
        # No constraints, compatible with any type
        return True
        
    def _compute_hash(self) -> int:
        return hash(("typevar", self.name, self.bound, self.constraints))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, TypeVar) and
                self.name == other.name and
                self.bound == other.bound and
                self.constraints == other.constraints)


@dataclass(frozen=True)
class TupleType(JacType):
    """Type representing tuple types."""
    
    element_types: Tuple[JacType, ...]
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=self._create_display_name(),
            flags=JacTypeFlags.INSTANTIABLE
        )
        
    def _create_display_name(self) -> str:
        """Create display name for tuple type."""
        if not self.element_types:
            return "tuple[()]"
        elements = ", ".join(t.display_name for t in self.element_types)
        return f"tuple[{elements}]"
        
    def _get_default_display_name(self) -> str:
        return self._create_display_name()
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Tuple compatibility based on element types."""
        if isinstance(other, TupleType):
            return (len(self.element_types) == len(other.element_types) and
                   all(t1.is_compatible_with(t2) for t1, t2 in 
                       zip(self.element_types, other.element_types)))
        return False
        
    def _compute_hash(self) -> int:
        return hash(("tuple", self.element_types))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, TupleType) and
                self.element_types == other.element_types)


@dataclass(frozen=True)
class ListType(JacType):
    """Type representing list types."""
    
    element_type: JacType
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=f"list[{self.element_type.display_name}]",
            flags=JacTypeFlags.INSTANTIABLE
        )
        
    def _get_default_display_name(self) -> str:
        return f"list[{self.element_type.display_name}]"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """List compatibility based on element type."""
        if isinstance(other, ListType):
            return self.element_type.is_compatible_with(other.element_type)
        return False
        
    def _compute_hash(self) -> int:
        return hash(("list", self.element_type))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, ListType) and
                self.element_type == other.element_type)


@dataclass(frozen=True)
class DictType(JacType):
    """Type representing dictionary types."""
    
    key_type: JacType
    value_type: JacType
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=f"dict[{self.key_type.display_name}, {self.value_type.display_name}]",
            flags=JacTypeFlags.INSTANTIABLE
        )
        
    def _get_default_display_name(self) -> str:
        return f"dict[{self.key_type.display_name}, {self.value_type.display_name}]"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Dict compatibility based on key and value types."""
        if isinstance(other, DictType):
            return (self.key_type.is_compatible_with(other.key_type) and
                   self.value_type.is_compatible_with(other.value_type))
        return False
        
    def _compute_hash(self) -> int:
        return hash(("dict", self.key_type, self.value_type))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return (isinstance(other, DictType) and
                self.key_type == other.key_type and
                self.value_type == other.value_type)


@dataclass(frozen=True)
class LiteralType(JacType):
    """Type representing literal value types."""
    
    value: Any
    
    def __post_init__(self) -> None:
        self._init_base_fields(
            display_name=f"Literal[{repr(self.value)}]"
        )
        
    def _get_default_display_name(self) -> str:
        return f"Literal[{repr(self.value)}]"
        
    def is_compatible_with(self, other: JacType) -> bool:
        """Literal compatibility based on value equality."""
        if isinstance(other, LiteralType):
            return self.value == other.value
        # Literal types are compatible with their base type
        # This would need integration with builtin type system
        return False
        
    def _compute_hash(self) -> int:
        return hash(("literal", self.value))
        
    def _is_equal_to(self, other: JacType) -> bool:
        return isinstance(other, LiteralType) and self.value == other.value


# Singleton instances for common types
UNKNOWN_TYPE = UnknownType()
ANY_TYPE = AnyType()
NONE_TYPE = NoneType()

# Common builtin types
INT_TYPE = BuiltinType("int", int)
FLOAT_TYPE = BuiltinType("float", float)
STR_TYPE = BuiltinType("str", str)
BOOL_TYPE = BuiltinType("bool", bool)
