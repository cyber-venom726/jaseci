"""Type factory for creating and managing type instances.

This module provides factory methods for creating type instances with
proper caching and canonicalization. Inspired by Pyright's type factory
pattern for efficient type management.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List as PyList, Optional, Tuple, Union

import jaclang.compiler.unitree as uni
from jaclang.compiler.unitree import Symbol

from .types import (
    ANY_TYPE,
    BOOL_TYPE,
    FLOAT_TYPE,
    INT_TYPE,
    NONE_TYPE,
    STR_TYPE,
    UNKNOWN_TYPE,
    ArchetypeType,
    BuiltinType,
    CallableType,
    DictType,
    EdgeType,
    GenericType,
    JacType,
    ListType,
    LiteralType,
    NodeType,
    TupleType,
    TypeVar,
    UnionType,
    WalkerType,
)
from .type_cache import TypeCache


class TypeFactory:
    """Factory for creating and caching type instances.
    
    Provides static methods for creating types with proper caching
    and canonicalization to ensure type identity and performance.
    """
    
    _cache = TypeCache()
    
    # Builtin type mappings
    _builtin_types: Dict[str, BuiltinType] = {
        "int": INT_TYPE,
        "float": FLOAT_TYPE, 
        "str": STR_TYPE,
        "bool": BOOL_TYPE,
        "any": ANY_TYPE,
        "None": NONE_TYPE,
    }
    
    @classmethod
    def get_builtin_type(cls, name: str) -> Optional[BuiltinType]:
        """Get a builtin type by name."""
        return cls._builtin_types.get(name)
        
    @classmethod
    def create_unknown_type(cls) -> JacType:
        """Create an unknown type instance."""
        return UNKNOWN_TYPE
        
    @classmethod
    def create_any_type(cls) -> JacType:
        """Create an any type instance."""
        return ANY_TYPE
        
    @classmethod
    def create_none_type(cls) -> JacType:
        """Create a none type instance."""
        return NONE_TYPE
        
    @classmethod
    def create_builtin_type(cls, name: str, python_type: Optional[type] = None) -> BuiltinType:
        """Create a builtin type with caching."""
        cache_key = f"builtin:{name}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        builtin_type = BuiltinType(name=name, python_type=python_type)
        cls._cache.set_type(cache_key, builtin_type)
        return builtin_type
        
    @classmethod
    def create_archetype_type(
        cls,
        name: str,
        symbol: Optional[Symbol] = None,
        base_types: Optional[Tuple[JacType, ...]] = None,
        type_parameters: Optional[Tuple[TypeVar, ...]] = None,
        members: Optional[Dict[str, JacType]] = None,
    ) -> ArchetypeType:
        """Create an archetype type with caching."""
        base_types = base_types or tuple()
        type_parameters = type_parameters or tuple()
        
        cache_key = f"archetype:{name}:{hash(base_types)}:{hash(type_parameters)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        archetype_type = ArchetypeType(
            name=name,
            symbol=symbol,
            base_types=base_types,
            type_parameters=type_parameters,
            members=members,
        )
        cls._cache.set_type(cache_key, archetype_type)
        return archetype_type
        
    @classmethod
    def create_walker_type(
        cls,
        name: str,
        symbol: Optional[Symbol] = None,
        abilities: Optional[Tuple[CallableType, ...]] = None,
    ) -> WalkerType:
        """Create a walker type with caching."""
        abilities = abilities or tuple()
        
        cache_key = f"walker:{name}:{hash(abilities)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        walker_type = WalkerType(name=name, symbol=symbol, abilities=abilities)
        cls._cache.set_type(cache_key, walker_type)
        return walker_type
        
    @classmethod
    def create_edge_type(
        cls,
        name: str,
        symbol: Optional[Symbol] = None,
    ) -> EdgeType:
        """Create an edge type with caching."""
        cache_key = f"edge:{name}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        edge_type = EdgeType(name=name, symbol=symbol)
        cls._cache.set_type(cache_key, edge_type)
        return edge_type
        
    @classmethod
    def create_node_type(
        cls,
        name: str,
        symbol: Optional[Symbol] = None,
    ) -> NodeType:
        """Create a node type with caching."""
        cache_key = f"node:{name}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        node_type = NodeType(name=name, symbol=symbol)
        cls._cache.set_type(cache_key, node_type)
        return node_type
        
    @classmethod
    def create_callable_type(
        cls,
        name: str,
        parameters: Optional[Tuple[JacType, ...]] = None,
        return_type: Optional[JacType] = None,
        is_method: bool = False,
        is_ability: bool = False,
    ) -> CallableType:
        """Create a callable type with caching."""
        parameters = parameters or tuple()
        
        cache_key = (f"callable:{name}:{hash(parameters)}:"
                    f"{hash(return_type)}:{is_method}:{is_ability}")
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        callable_type = CallableType(
            name=name,
            parameters=parameters,
            return_type=return_type,
            is_method=is_method,
            is_ability=is_ability,
        )
        cls._cache.set_type(cache_key, callable_type)
        return callable_type
        
    @classmethod
    def create_union_type(cls, types: Union[PyList[JacType], Tuple[JacType, ...]]) -> JacType:
        """Create a union type with automatic simplification."""
        if not types:
            return UNKNOWN_TYPE
            
        if len(types) == 1:
            return types[0]
            
        # Convert to frozenset for deduplication and ordering
        type_set = frozenset(types)
        
        # If only one unique type, return it
        if len(type_set) == 1:
            return next(iter(type_set))
            
        # Check cache
        cache_key = f"union:{hash(type_set)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        union_type = UnionType(types=type_set)
        cls._cache.set_type(cache_key, union_type)
        return union_type
        
    @classmethod
    def create_generic_type(
        cls,
        base_type: JacType,
        type_arguments: Optional[Tuple[JacType, ...]] = None,
    ) -> GenericType:
        """Create a generic type with caching."""
        type_arguments = type_arguments or tuple()
        
        cache_key = f"generic:{hash(base_type)}:{hash(type_arguments)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        generic_type = GenericType(base_type=base_type, type_arguments=type_arguments)
        cls._cache.set_type(cache_key, generic_type)
        return generic_type
        
    @classmethod
    def create_type_var(
        cls,
        name: str,
        bound: Optional[JacType] = None,
        constraints: Optional[Tuple[JacType, ...]] = None,
    ) -> TypeVar:
        """Create a type variable with caching."""
        constraints = constraints or tuple()
        
        cache_key = f"typevar:{name}:{hash(bound)}:{hash(constraints)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        type_var = TypeVar(name=name, bound=bound, constraints=constraints)
        cls._cache.set_type(cache_key, type_var)
        return type_var
        
    @classmethod
    def create_tuple_type(cls, element_types: Tuple[JacType, ...]) -> TupleType:
        """Create a tuple type with caching."""
        cache_key = f"tuple:{hash(element_types)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        tuple_type = TupleType(element_types=element_types)
        cls._cache.set_type(cache_key, tuple_type)
        return tuple_type
        
    @classmethod
    def create_list_type(cls, element_type: JacType) -> ListType:
        """Create a list type with caching."""
        cache_key = f"list:{hash(element_type)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        list_type = ListType(element_type=element_type)
        cls._cache.set_type(cache_key, list_type)
        return list_type
        
    @classmethod
    def create_dict_type(cls, key_type: JacType, value_type: JacType) -> DictType:
        """Create a dict type with caching."""
        cache_key = f"dict:{hash(key_type)}:{hash(value_type)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        dict_type = DictType(key_type=key_type, value_type=value_type)
        cls._cache.set_type(cache_key, dict_type)
        return dict_type
        
    @classmethod
    def create_literal_type(cls, value: object) -> LiteralType:
        """Create a literal type with caching."""
        cache_key = f"literal:{hash(value)}"
        cached = cls._cache.get_type(cache_key)
        if cached:
            return cached
            
        literal_type = LiteralType(value=value)
        cls._cache.set_type(cache_key, literal_type)
        return literal_type
        
    @classmethod
    def create_optional_type(cls, inner_type: JacType) -> JacType:
        """Create an optional type (Union[T, None])."""
        return cls.create_union_type([inner_type, NONE_TYPE])
        
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the type cache."""
        cls._cache.clear()
        
    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """Get cache statistics."""
        return cls._cache.get_stats()
        
    @classmethod
    def from_ast_type_annotation(cls, ast_node: uni.UniNode) -> JacType:
        """Create a type from an AST type annotation node.
        
        This method handles the conversion from Jac AST type annotations
        to the internal type representation.
        """
        if isinstance(ast_node, uni.Name):
            # Simple type name
            name = ast_node.value
            builtin = cls.get_builtin_type(name)
            if builtin:
                return builtin
            # TODO: Look up in symbol table for user-defined types
            return cls.create_archetype_type(name)
            
        elif isinstance(ast_node, uni.AtomTrailer):
            # Generic type like list[int] or dict[str, int]
            if hasattr(ast_node, 'target') and hasattr(ast_node, 'trailer'):
                base_name = ast_node.target.value if hasattr(ast_node.target, 'value') else str(ast_node.target)
                
                # Handle generic types
                if hasattr(ast_node.trailer, 'items'):
                    type_args = tuple(cls.from_ast_type_annotation(arg) 
                                    for arg in ast_node.trailer.items)
                    
                    # Built-in generics
                    if base_name == "list" and len(type_args) == 1:
                        return cls.create_list_type(type_args[0])
                    elif base_name == "dict" and len(type_args) == 2:
                        return cls.create_dict_type(type_args[0], type_args[1])
                    elif base_name == "tuple":
                        return cls.create_tuple_type(type_args)
                    else:
                        # User-defined generic
                        base_type = cls.create_archetype_type(base_name)
                        return cls.create_generic_type(base_type, type_args)
                        
                return cls.create_archetype_type(base_name)
                
        elif isinstance(ast_node, uni.BinaryExpr):
            # Union types like int | str
            if hasattr(ast_node, 'op') and ast_node.op == '|':
                left = cls.from_ast_type_annotation(ast_node.left)
                right = cls.from_ast_type_annotation(ast_node.right)
                return cls.create_union_type([left, right])
                
        # Fallback to unknown type
        return UNKNOWN_TYPE
