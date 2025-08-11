# Jac Type Factory Implementation Guide

## Table of Contents
1. [Overview](#overview)
2. [Pyright's Type Creation Strategy](#pyrights-type-creation-strategy)
3. [Type Factory Architecture for Jac](#type-factory-architecture-for-jac)
4. [Core Type Creation Functions](#core-type-creation-functions)
5. [Type Caching Strategy](#type-caching-strategy)
6. [Jac-Specific Type Extensions](#jac-specific-type-extensions)
7. [Implementation Examples](#implementation-examples)
8. [Performance Considerations](#performance-considerations)
9. [Integration with Compiler](#integration-with-compiler)

---

## Overview

In type checkers like Pyright, there isn't a single "TypeFactory" class. Instead, **type creation is distributed across namespace-based factory functions** attached to each type class. This approach provides better organization, performance, and type safety compared to a centralized factory pattern.

### Key Insights from Pyright

1. **Namespace-based Factories**: Each type (ClassType, FunctionType, TypeVarType, etc.) has its own namespace with creation functions
2. **Multiple Creation Patterns**: Different creation functions for different use cases (instance vs instantiable, cloning, specialization)
3. **Integrated Caching**: Type instances are cached directly on the type objects for performance
4. **Immutable with Cloning**: Types are immutable; modifications create new instances via cloning

---

## Pyright's Type Creation Strategy

### 1. Namespace-Based Type Creators

```typescript
// Pyright's approach - each type has its own creation namespace
export namespace ClassType {
    export function createInstantiable(
        name: string,
        fullName: string,
        moduleName: string,
        fileUri: Uri,
        flags: ClassTypeFlags,
        typeSourceId: TypeSourceId,
        declaredMetaclass: ClassType | UnknownType | undefined,
        effectiveMetaclass: ClassType | UnknownType | undefined,
        docString?: string
    ): ClassType

    export function cloneAsInstance(type: ClassType, includeSubclasses = true): ClassType
    export function specialize(classType: ClassType, typeArgs: Type[]): ClassType
    // ... many more specialized creators
}

export namespace FunctionType {
    export function createInstance(name: string, fullName: string, moduleName: string, 
                                 functionFlags: FunctionTypeFlags, docString?: string): FunctionType
    export function createInstantiable(functionFlags: FunctionTypeFlags, docString?: string): FunctionType
    export function createSynthesizedInstance(name: string, additionalFlags = FunctionTypeFlags.None): FunctionType
    export function clone(type: FunctionType, stripFirstParam = false, boundToType?: ClassType): FunctionType
}

export namespace TypeVarType {
    export function createInstance(name: string, kind: TypeVarKind = TypeVarKind.TypeVar): TypeVarType
    export function createInstantiable(name: string, kind: TypeVarKind = TypeVarKind.TypeVar): TypeVarType
    export function cloneForNewName(type: TypeVarType, name: string): TypeVarType
    export function cloneForScopeId(type: TypeVarType, scopeId: string, scopeName: string): TypeVarType
}
```

### 2. Built-in Type Singletons

```typescript
// Simple types are created as singletons
export namespace UnknownType {
    const _instance: UnknownType = {
        category: TypeCategory.Unknown,
        flags: TypeFlags.Instantiable | TypeFlags.Instance,
        props: undefined,
        cached: undefined,
    };

    export function create() {
        return _instance;
    }
}

export namespace AnyType {
    const _instance: AnyType = {
        category: TypeCategory.Any,
        flags: TypeFlags.Instantiable | TypeFlags.Instance,
        props: undefined,
        cached: undefined,
    };

    export function create() {
        return _instance;
    }
}
```

### 3. Caching Strategy

Types cache their converted versions directly on the type object:

```typescript
interface CachedTypeInfo {
    // Type converted to instantiable and instance by convertToInstance
    // and convertToInstantiable (cached)
    instantiableType?: Type;
    instanceType?: Type;

    // Requires specialization flag (cached)
    requiresSpecialization?: boolean;
}

// Usage in cloning functions
export function cloneAsInstance(type: ClassType, includeSubclasses = true): ClassType {
    if (includeSubclasses && type.cached?.typeBaseInstanceType) {
        return type.cached.typeBaseInstanceType as ClassType;
    }
    
    const newInstance = TypeBase.cloneTypeAsInstance(type, /* cache */ includeSubclasses);
    // ... rest of implementation
}
```

---

## Type Factory Architecture for Jac

Based on Pyright's proven approach, here's how we can implement type factories for Jac:

### 1. Core Type Hierarchy

```python
# jac/jaclang/compiler/type_system/types.py

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, List, Any, Union as PyUnion
from dataclasses import dataclass, field

class TypeCategory(Enum):
    """Type categories following Pyright's taxonomy but extended for Jac"""
    # Core Python-compatible types
    UNKNOWN = "Unknown"
    ANY = "Any"
    NEVER = "Never"
    CLASS = "Class"
    FUNCTION = "Function"
    UNION = "Union"
    TYPE_VAR = "TypeVar"
    MODULE = "Module"
    
    # Jac-specific types
    WALKER = "Walker"
    ARCHETYPE = "Archetype"  # Node/Edge archetypes
    ABILITY = "Ability"
    EDGE = "Edge"
    NODE = "Node"

class TypeFlags(Enum):
    """Type flags for instantiable vs instance distinction"""
    NONE = 0
    INSTANTIABLE = 1 << 0
    INSTANCE = 1 << 1
    AMBIGUOUS = 1 << 2  # For gradual typing

@dataclass
class TypeBase(ABC):
    """Base class for all types, following Pyright's structure"""
    category: TypeCategory
    flags: TypeFlags
    cached: Optional[Dict[str, Any]] = field(default_factory=dict)
    props: Optional[Dict[str, Any]] = None
    
    def is_instantiable(self) -> bool:
        return TypeFlags.INSTANTIABLE in self.flags
        
    def is_instance(self) -> bool:
        return TypeFlags.INSTANCE in self.flags
```

### 2. Type Creation Namespaces

```python
# jac/jaclang/compiler/type_system/type_factory.py

from typing import Optional, List, Dict
from .types import *

class UnknownType(TypeBase):
    """The unknown type for gradual typing"""
    
    _instance: Optional['UnknownType'] = None
    
    @classmethod
    def create(cls) -> 'UnknownType':
        """Singleton pattern for Unknown type"""
        if cls._instance is None:
            cls._instance = cls(
                category=TypeCategory.UNKNOWN,
                flags=TypeFlags.INSTANTIABLE | TypeFlags.INSTANCE
            )
        return cls._instance

class AnyType(TypeBase):
    """The Any type for dynamic typing"""
    
    _instance: Optional['AnyType'] = None
    
    @classmethod
    def create(cls) -> 'AnyType':
        """Singleton pattern for Any type"""
        if cls._instance is None:
            cls._instance = cls(
                category=TypeCategory.ANY,
                flags=TypeFlags.INSTANTIABLE | TypeFlags.INSTANCE
            )
        return cls._instance

@dataclass
class ClassType(TypeBase):
    """Represents classes and Jac archetypes"""
    name: str = ""
    full_name: str = ""
    module_name: str = ""
    base_classes: List['Type'] = field(default_factory=list)
    members: Dict[str, 'Symbol'] = field(default_factory=dict)
    type_params: List['TypeVarType'] = field(default_factory=list)
    is_archetype: bool = False  # Jac-specific flag
    archetype_kind: Optional[str] = None  # "node", "edge", or None
    
    @classmethod
    def create_instantiable(cls, 
                          name: str, 
                          full_name: str, 
                          module_name: str,
                          is_archetype: bool = False,
                          archetype_kind: Optional[str] = None) -> 'ClassType':
        """Create an instantiable class type"""
        return cls(
            category=TypeCategory.ARCHETYPE if is_archetype else TypeCategory.CLASS,
            flags=TypeFlags.INSTANTIABLE,
            name=name,
            full_name=full_name,
            module_name=module_name,
            is_archetype=is_archetype,
            archetype_kind=archetype_kind
        )
    
    @classmethod
    def clone_as_instance(cls, class_type: 'ClassType') -> 'ClassType':
        """Clone as instance type with caching"""
        cache_key = "instance_type"
        if cache_key in class_type.cached:
            return class_type.cached[cache_key]
            
        instance = cls(
            category=class_type.category,
            flags=TypeFlags.INSTANCE,
            name=class_type.name,
            full_name=class_type.full_name,
            module_name=class_type.module_name,
            base_classes=class_type.base_classes.copy(),
            members=class_type.members.copy(),
            type_params=class_type.type_params.copy(),
            is_archetype=class_type.is_archetype,
            archetype_kind=class_type.archetype_kind
        )
        
        # Cache for future use
        class_type.cached[cache_key] = instance
        return instance
    
    @classmethod
    def specialize(cls, 
                  class_type: 'ClassType', 
                  type_args: List['Type']) -> 'ClassType':
        """Create specialized version with type arguments"""
        specialized = cls(
            category=class_type.category,
            flags=class_type.flags,
            name=class_type.name,
            full_name=class_type.full_name,
            module_name=class_type.module_name,
            base_classes=class_type.base_classes.copy(),
            members=class_type.members.copy(),
            type_params=class_type.type_params.copy(),
            is_archetype=class_type.is_archetype,
            archetype_kind=class_type.archetype_kind
        )
        # Store type arguments in props
        if specialized.props is None:
            specialized.props = {}
        specialized.props['type_args'] = type_args
        return specialized

@dataclass 
class FunctionType(TypeBase):
    """Represents functions and Jac abilities"""
    name: str = ""
    full_name: str = ""
    module_name: str = ""
    parameters: List['FunctionParam'] = field(default_factory=list)
    return_type: Optional['Type'] = None
    is_ability: bool = False  # Jac-specific flag
    ability_target: Optional['Type'] = None  # Target archetype for abilities
    
    @classmethod
    def create_instance(cls,
                       name: str,
                       full_name: str = "",
                       module_name: str = "",
                       is_ability: bool = False) -> 'FunctionType':
        """Create a function instance"""
        return cls(
            category=TypeCategory.ABILITY if is_ability else TypeCategory.FUNCTION,
            flags=TypeFlags.INSTANCE,
            name=name,
            full_name=full_name or name,
            module_name=module_name,
            is_ability=is_ability
        )
    
    @classmethod 
    def create_synthesized_ability(cls, name: str, target_type: 'Type') -> 'FunctionType':
        """Create a synthesized ability for an archetype"""
        ability = cls.create_instance(name, is_ability=True)
        ability.ability_target = target_type
        return ability

@dataclass
class WalkerType(TypeBase):
    """Jac-specific walker type"""
    name: str = ""
    full_name: str = ""
    module_name: str = ""
    abilities: List[FunctionType] = field(default_factory=list)
    
    @classmethod
    def create_instantiable(cls, 
                          name: str,
                          full_name: str,
                          module_name: str) -> 'WalkerType':
        """Create an instantiable walker type"""
        return cls(
            category=TypeCategory.WALKER,
            flags=TypeFlags.INSTANTIABLE,
            name=name,
            full_name=full_name,
            module_name=module_name
        )

@dataclass
class TypeVarType(TypeBase):
    """Type variable for generics"""
    name: str = ""
    constraints: List['Type'] = field(default_factory=list)
    bound_type: Optional['Type'] = None
    
    @classmethod
    def create_instance(cls, name: str) -> 'TypeVarType':
        """Create a type variable instance"""
        return cls(
            category=TypeCategory.TYPE_VAR,
            flags=TypeFlags.INSTANCE,
            name=name
        )
    
    @classmethod
    def create_instantiable(cls, name: str) -> 'TypeVarType':
        """Create an instantiable type variable"""
        return cls(
            category=TypeCategory.TYPE_VAR,
            flags=TypeFlags.INSTANTIABLE,
            name=name
        )

# Union type for combining multiple types
Type = PyUnion[UnknownType, AnyType, ClassType, FunctionType, WalkerType, TypeVarType]
```

---

## Core Type Creation Functions

### 1. Centralized Type Factory (Optional Layer)

```python
# jac/jaclang/compiler/type_system/type_factory.py

class TypeFactory:
    """Centralized factory for common type creation patterns"""
    
    def __init__(self):
        self._builtin_types: Dict[str, Type] = {}
        self._init_builtin_types()
    
    def _init_builtin_types(self):
        """Initialize built-in types"""
        self._builtin_types.update({
            'Unknown': UnknownType.create(),
            'Any': AnyType.create(),
            'int': ClassType.create_instantiable('int', 'builtins.int', 'builtins'),
            'str': ClassType.create_instantiable('str', 'builtins.str', 'builtins'),
            'bool': ClassType.create_instantiable('bool', 'builtins.bool', 'builtins'),
            'float': ClassType.create_instantiable('float', 'builtins.float', 'builtins'),
            'list': ClassType.create_instantiable('list', 'builtins.list', 'builtins'),
            'dict': ClassType.create_instantiable('dict', 'builtins.dict', 'builtins'),
        })
    
    def get_builtin_type(self, name: str) -> Optional[Type]:
        """Get a built-in type by name"""
        return self._builtin_types.get(name)
    
    def create_archetype_type(self, 
                            name: str, 
                            kind: str,  # "node" or "edge"
                            module_name: str = "") -> ClassType:
        """Create a Jac archetype type"""
        return ClassType.create_instantiable(
            name=name,
            full_name=f"{module_name}.{name}" if module_name else name,
            module_name=module_name,
            is_archetype=True,
            archetype_kind=kind
        )
    
    def create_walker_type(self, 
                          name: str, 
                          module_name: str = "") -> WalkerType:
        """Create a Jac walker type"""
        return WalkerType.create_instantiable(
            name=name,
            full_name=f"{module_name}.{name}" if module_name else name,
            module_name=module_name
        )
    
    def create_ability_type(self, 
                           name: str, 
                           target_archetype: Type,
                           module_name: str = "") -> FunctionType:
        """Create a Jac ability type"""
        ability = FunctionType.create_synthesized_ability(name, target_archetype)
        ability.module_name = module_name
        return ability
    
    def create_generic_type(self, 
                          base_type: Type, 
                          type_args: List[Type]) -> Type:
        """Create a generic type with type arguments"""
        if isinstance(base_type, ClassType):
            return ClassType.specialize(base_type, type_args)
        # Handle other generic types as needed
        return base_type
```

---

## Type Caching Strategy

### 1. Multi-Level Caching

```python
# jac/jaclang/compiler/type_system/type_cache.py

from typing import Dict, Optional, Tuple, Any
from weakref import WeakValueDictionary
import hashlib

class TypeCache:
    """High-performance type caching system"""
    
    def __init__(self):
        # Level 1: Type instance cache (weak references)
        self._type_instances: WeakValueDictionary[str, Type] = WeakValueDictionary()
        
        # Level 2: Computed properties cache  
        self._property_cache: Dict[Tuple[int, str], Any] = {}
        
        # Level 3: Specialized type cache
        self._specialized_cache: Dict[str, Type] = {}
        
        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_or_create_type(self, 
                          cache_key: str, 
                          creator_func: callable) -> Type:
        """Get cached type or create new one"""
        if cache_key in self._type_instances:
            self._cache_hits += 1
            return self._type_instances[cache_key]
        
        # Create new type
        self._cache_misses += 1
        new_type = creator_func()
        self._type_instances[cache_key] = new_type
        return new_type
    
    def create_cache_key(self, *args) -> str:
        """Create cache key from arguments"""
        key_data = "|".join(str(arg) for arg in args)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def cache_property(self, 
                      type_obj: Type, 
                      property_name: str, 
                      value: Any) -> None:
        """Cache computed property on type"""
        key = (id(type_obj), property_name)
        self._property_cache[key] = value
    
    def get_cached_property(self, 
                           type_obj: Type, 
                           property_name: str) -> Optional[Any]:
        """Get cached property from type"""
        key = (id(type_obj), property_name) 
        return self._property_cache.get(key)
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': round(hit_rate, 2),
            'total_types': len(self._type_instances)
        }
```

### 2. Cache Integration Example

```python
# Enhanced type factory with caching
class CachedTypeFactory(TypeFactory):
    """Type factory with integrated caching"""
    
    def __init__(self):
        super().__init__()
        self.cache = TypeCache()
    
    def create_archetype_type(self, 
                            name: str, 
                            kind: str,
                            module_name: str = "") -> ClassType:
        """Create archetype with caching"""
        cache_key = self.cache.create_cache_key(
            'archetype', name, kind, module_name
        )
        
        return self.cache.get_or_create_type(
            cache_key,
            lambda: super().create_archetype_type(name, kind, module_name)
        )
    
    def get_mro(self, class_type: ClassType) -> List[Type]:
        """Get Method Resolution Order with caching"""
        cached_mro = self.cache.get_cached_property(class_type, 'mro')
        if cached_mro is not None:
            return cached_mro
        
        # Compute MRO
        mro = self._compute_mro(class_type)
        self.cache.cache_property(class_type, 'mro', mro)
        return mro
```

---

## Jac-Specific Type Extensions

### 1. Graph-Aware Types

```python
# jac/jaclang/compiler/type_system/jac_types.py

@dataclass
class EdgeType(ClassType):
    """Specialized edge archetype type"""
    source_type: Optional[Type] = None
    target_type: Optional[Type] = None
    
    @classmethod
    def create_edge_archetype(cls,
                            name: str,
                            source_type: Optional[Type] = None,
                            target_type: Optional[Type] = None,
                            module_name: str = "") -> 'EdgeType':
        """Create edge archetype with connection constraints"""
        edge = cls(
            category=TypeCategory.EDGE,
            flags=TypeFlags.INSTANTIABLE,
            name=name,
            full_name=f"{module_name}.{name}" if module_name else name,
            module_name=module_name,
            is_archetype=True,
            archetype_kind="edge",
            source_type=source_type,
            target_type=target_type
        )
        return edge

@dataclass
class NodeType(ClassType):
    """Specialized node archetype type"""
    incoming_edges: List[Type] = field(default_factory=list)
    outgoing_edges: List[Type] = field(default_factory=list)
    
    @classmethod
    def create_node_archetype(cls,
                            name: str,
                            module_name: str = "") -> 'NodeType':
        """Create node archetype"""
        return cls(
            category=TypeCategory.NODE,
            flags=TypeFlags.INSTANTIABLE,
            name=name,
            full_name=f"{module_name}.{name}" if module_name else name,
            module_name=module_name,
            is_archetype=True,
            archetype_kind="node"
        )

class GraphTypeAnalyzer:
    """Analyze graph type relationships"""
    
    def __init__(self, type_factory: TypeFactory):
        self.type_factory = type_factory
    
    def validate_edge_connection(self, 
                               edge_type: EdgeType,
                               source_type: Type,
                               target_type: Type) -> bool:
        """Validate if edge can connect two node types"""
        if edge_type.source_type:
            if not self._is_compatible(source_type, edge_type.source_type):
                return False
        
        if edge_type.target_type:
            if not self._is_compatible(target_type, edge_type.target_type):
                return False
                
        return True
    
    def _is_compatible(self, actual: Type, expected: Type) -> bool:
        """Check type compatibility"""
        # Implement type compatibility logic
        # This is a simplified version
        if actual == expected:
            return True
        
        # Check inheritance hierarchy
        if isinstance(actual, ClassType) and isinstance(expected, ClassType):
            return expected in self._get_base_classes(actual)
        
        return False
```

---

## Implementation Examples

### 1. Basic Usage

```python
# Example usage of the type factory system

def example_basic_usage():
    """Basic type factory usage"""
    factory = CachedTypeFactory()
    
    # Create built-in types
    int_type = factory.get_builtin_type('int')
    str_type = factory.get_builtin_type('str')
    
    # Create Jac-specific types
    person_node = factory.create_archetype_type('Person', 'node', 'mymodule')
    friendship_edge = factory.create_archetype_type('Friendship', 'edge', 'mymodule')
    visitor_walker = factory.create_walker_type('Visitor', 'mymodule')
    
    # Create generic types
    list_of_int = factory.create_generic_type(
        factory.get_builtin_type('list'),
        [int_type]
    )
    
    print(f"Created types: {person_node.name}, {friendship_edge.name}")
    print(f"Cache stats: {factory.cache.get_stats()}")

def example_edge_type_with_constraints():
    """Example of creating edge type with connection constraints"""
    factory = CachedTypeFactory()
    
    # Create node types
    person_type = NodeType.create_node_archetype('Person', 'social')
    company_type = NodeType.create_node_archetype('Company', 'social')
    
    # Create edge type with constraints
    employment_edge = EdgeType.create_edge_archetype(
        'Employment',
        source_type=person_type,  # Only Person can be employed
        target_type=company_type, # Only by Company
        module_name='social'
    )
    
    # Validate connections
    analyzer = GraphTypeAnalyzer(factory)
    valid = analyzer.validate_edge_connection(
        employment_edge, person_type, company_type
    )
    print(f"Employment edge connection valid: {valid}")

def example_ability_creation():
    """Example of creating abilities for archetypes"""
    factory = CachedTypeFactory()
    
    # Create archetype
    person_type = factory.create_archetype_type('Person', 'node')
    
    # Create ability for the archetype
    greet_ability = factory.create_ability_type(
        'greet', person_type, 'social'
    )
    
    # Abilities are functions with special properties
    assert greet_ability.is_ability == True
    assert greet_ability.ability_target == person_type
```

### 2. Integration with Type Evaluator

```python
# jac/jaclang/compiler/type_system/evaluator.py

class TypeEvaluator:
    """Main type evaluation engine"""
    
    def __init__(self, type_factory: TypeFactory):
        self.type_factory = type_factory
        self.symbol_table: Dict[str, Type] = {}
    
    def evaluate_expression_type(self, expr_node) -> Type:
        """Evaluate the type of an expression"""
        if expr_node.type == 'NameExpr':
            return self._evaluate_name(expr_node)
        elif expr_node.type == 'CallExpr':
            return self._evaluate_call(expr_node)
        elif expr_node.type == 'LiteralExpr':
            return self._evaluate_literal(expr_node)
        else:
            return self.type_factory.get_builtin_type('Unknown')
    
    def _evaluate_name(self, name_node) -> Type:
        """Evaluate named reference"""
        name = name_node.name
        if name in self.symbol_table:
            return self.symbol_table[name]
        
        # Try built-in types
        builtin = self.type_factory.get_builtin_type(name)
        if builtin:
            return builtin
            
        return self.type_factory.get_builtin_type('Unknown')
    
    def _evaluate_literal(self, literal_node) -> Type:
        """Evaluate literal type"""
        if literal_node.value_type == 'int':
            return self.type_factory.get_builtin_type('int')
        elif literal_node.value_type == 'str':
            return self.type_factory.get_builtin_type('str')
        elif literal_node.value_type == 'bool':
            return self.type_factory.get_builtin_type('bool')
        else:
            return self.type_factory.get_builtin_type('Unknown')
```

---

## Performance Considerations

### 1. Memory Management

```python
# Memory-efficient type sharing
class TypeInterningFactory(TypeFactory):
    """Type factory with string interning for memory efficiency"""
    
    def __init__(self):
        super().__init__()
        self._interned_strings: Dict[str, str] = {}
    
    def _intern_string(self, s: str) -> str:
        """Intern string to save memory"""
        if s not in self._interned_strings:
            self._interned_strings[s] = s
        return self._interned_strings[s]
    
    def create_archetype_type(self, name: str, kind: str, module_name: str = "") -> ClassType:
        """Create with interned strings"""
        return ClassType.create_instantiable(
            name=self._intern_string(name),
            full_name=self._intern_string(f"{module_name}.{name}" if module_name else name),
            module_name=self._intern_string(module_name),
            is_archetype=True,
            archetype_kind=self._intern_string(kind)
        )
```

### 2. Lazy Evaluation

```python
class LazyTypeProperty:
    """Lazy evaluation of expensive type properties"""
    
    def __init__(self, compute_func):
        self.compute_func = compute_func
        self.cached_value = None
        self.computed = False
    
    def __get__(self, obj, objtype=None):
        if not self.computed:
            self.cached_value = self.compute_func(obj)
            self.computed = True
        return self.cached_value

# Usage in type classes
class ClassType(TypeBase):
    """Class with lazy properties"""
    
    @LazyTypeProperty
    def mro(self) -> List[Type]:
        """Lazily computed method resolution order"""
        return self._compute_mro()
    
    def _compute_mro(self) -> List[Type]:
        """Expensive MRO computation"""
        # Implementation here
        pass
```

---

## Integration with Compiler

### 1. Compiler Pass Integration

```python
# jac/jaclang/compiler/passes/main/type_check_pass.py

from jaclang.compiler.passes.main import Pass
from jaclang.compiler.type_system import TypeFactory, TypeEvaluator

class TypeCheckPass(Pass):
    """Type checking compiler pass"""
    
    def __init__(self, prog):
        super().__init__(prog)
        self.type_factory = TypeFactory()
        self.type_evaluator = TypeEvaluator(self.type_factory)
    
    def enter_archetype_def(self, node):
        """Handle archetype definition"""
        archetype_type = self.type_factory.create_archetype_type(
            name=node.name,
            kind=node.kind,  # 'node' or 'edge'
            module_name=self.prog.mod.name
        )
        
        # Register in symbol table
        self.set_symbol_type(node.name, archetype_type)
        
        # Store on AST node for later use
        node.type = archetype_type
    
    def enter_walker_def(self, node):
        """Handle walker definition"""
        walker_type = self.type_factory.create_walker_type(
            name=node.name,
            module_name=self.prog.mod.name
        )
        
        self.set_symbol_type(node.name, walker_type)
        node.type = walker_type
    
    def enter_ability_def(self, node):
        """Handle ability definition"""
        # Find target archetype
        target_type = self.get_symbol_type(node.target)
        
        ability_type = self.type_factory.create_ability_type(
            name=node.name,
            target_archetype=target_type,
            module_name=self.prog.mod.name
        )
        
        # Add to target archetype's abilities
        if isinstance(target_type, ClassType) and target_type.is_archetype:
            target_type.members[node.name] = ability_type
```

### 2. Usage in JacProgram

```python
# Update to jac/jaclang/compiler/program.py

# Add to ir_gen_sched
ir_gen_sched = [
    SymTabBuildPass,
    DeclImplMatchPass,
    DefUsePass,
    SemDefMatchPass,
    TypeCheckPass,  # Add our type checking pass
    CFGBuildPass,
    InheritancePass,
]

class JacProgram:
    """Enhanced with type system"""
    
    def __init__(self, main_mod: Optional[uni.ProgramModule] = None) -> None:
        super().__init__(main_mod)
        self.type_factory = TypeFactory()
        self.type_errors: List[str] = []
    
    def get_type_info(self, file_path: str) -> Dict[str, Any]:
        """Get type information for a file"""
        if file_path in self.mod.hub:
            module = self.mod.hub[file_path]
            return {
                'symbols': getattr(module, 'symbol_types', {}),
                'errors': getattr(module, 'type_errors', []),
                'factory_stats': self.type_factory.cache.get_stats() if hasattr(self.type_factory, 'cache') else {}
            }
        return {}
```

---

## Conclusion

The type factory system for Jac follows Pyright's proven approach of **distributed namespace-based creation** rather than a single centralized factory. This provides:

### Key Benefits
1. **Performance**: Direct type creation with integrated caching
2. **Type Safety**: Each type manages its own creation logic
3. **Extensibility**: Easy to add new type-specific creation patterns
4. **Memory Efficiency**: Sophisticated caching and interning strategies
5. **Jac Integration**: Native support for graph-programming constructs

### Implementation Roadmap
1. **Phase 1**: Implement core type hierarchy and basic factory functions
2. **Phase 2**: Add caching layer and performance optimizations
3. **Phase 3**: Implement Jac-specific types (archetypes, walkers, abilities)
4. **Phase 4**: Integrate with compiler passes and type evaluator
5. **Phase 5**: Add advanced features like lazy evaluation and memory optimization

This approach ensures that Jac's type system will be both powerful and performant, supporting the unique requirements of graph-based programming while maintaining compatibility with Python's type system.
