"""Type caching system for performance optimization.

This module provides caching mechanisms for type instances to improve
performance by avoiding redundant type creation and enabling fast
type comparison through identity checks.
"""

from __future__ import annotations

import gc
import weakref
from typing import Any, Dict, Optional, Set
from weakref import WeakValueDictionary

from .types import JacType


class TypeCache:
    """Cache for type instances with weak references.
    
    Uses weak references to avoid memory leaks while providing
    fast type lookup and identity-based comparison.
    """
    
    def __init__(self) -> None:
        """Initialize the type cache."""
        self._type_cache: WeakValueDictionary[str, JacType] = WeakValueDictionary()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "total_types": 0,
        }
        
    def get_type(self, cache_key: str) -> Optional[JacType]:
        """Get a type from the cache by key."""
        result = self._type_cache.get(cache_key)
        if result is not None:
            self._stats["hits"] += 1
        else:
            self._stats["misses"] += 1
        return result
        
    def set_type(self, cache_key: str, type_instance: JacType) -> None:
        """Store a type in the cache."""
        self._type_cache[cache_key] = type_instance
        self._stats["total_types"] = len(self._type_cache)
        
    def has_type(self, cache_key: str) -> bool:
        """Check if a type exists in the cache."""
        return cache_key in self._type_cache
        
    def clear(self) -> None:
        """Clear the cache."""
        self._type_cache.clear()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "total_types": 0,
        }
        
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        self._stats["total_types"] = len(self._type_cache)
        return self._stats.copy()
        
    def compact(self) -> None:
        """Force garbage collection to clean up weak references."""
        gc.collect()
        self._stats["total_types"] = len(self._type_cache)


# Global type cache instance
_global_cache: Optional[TypeCache] = None


def get_global_cache() -> TypeCache:
    """Get the global type cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = TypeCache()
    return _global_cache


class TypeInternPool:
    """Pool for interning type instances to ensure identity.
    
    Similar to Python's string interning, this ensures that 
    equivalent types are the same object in memory.
    """
    
    def __init__(self) -> None:
        """Initialize the intern pool."""
        self._pool: WeakValueDictionary[int, JacType] = WeakValueDictionary()
        
    def intern_type(self, type_instance: JacType) -> JacType:
        """Intern a type instance, returning the canonical instance."""
        type_hash = hash(type_instance)
        existing = self._pool.get(type_hash)
        
        if existing is not None and existing == type_instance:
            return existing
            
        # Store the new instance
        self._pool[type_hash] = type_instance
        return type_instance
        
    def clear(self) -> None:
        """Clear the intern pool."""
        self._pool.clear()
        
    def size(self) -> int:
        """Get the current size of the pool."""
        return len(self._pool)


# Global intern pool
_global_intern_pool: Optional[TypeInternPool] = None


def get_global_intern_pool() -> TypeInternPool:
    """Get the global type intern pool."""
    global _global_intern_pool
    if _global_intern_pool is None:
        _global_intern_pool = TypeInternPool()
    return _global_intern_pool


class TypeCompatibilityCache:
    """Cache for type compatibility checks.
    
    Caches the results of expensive type compatibility computations
    to avoid redundant work during type checking.
    """
    
    def __init__(self, max_size: int = 10000) -> None:
        """Initialize the compatibility cache."""
        self._cache: Dict[tuple[int, int], bool] = {}
        self._max_size = max_size
        
    def get_compatibility(self, type1: JacType, type2: JacType) -> Optional[bool]:
        """Get cached compatibility result."""
        key = (hash(type1), hash(type2))
        return self._cache.get(key)
        
    def set_compatibility(self, type1: JacType, type2: JacType, result: bool) -> None:
        """Cache a compatibility result."""
        if len(self._cache) >= self._max_size:
            # Simple LRU: remove oldest entries
            # In a production system, you might want a more sophisticated strategy
            to_remove = list(self._cache.keys())[: self._max_size // 4]
            for key in to_remove:
                del self._cache[key]
                
        key = (hash(type1), hash(type2))
        self._cache[key] = result
        
    def clear(self) -> None:
        """Clear the compatibility cache."""
        self._cache.clear()
        
    def size(self) -> int:
        """Get the current cache size."""
        return len(self._cache)


# Global compatibility cache
_global_compatibility_cache: Optional[TypeCompatibilityCache] = None


def get_global_compatibility_cache() -> TypeCompatibilityCache:
    """Get the global type compatibility cache."""
    global _global_compatibility_cache
    if _global_compatibility_cache is None:
        _global_compatibility_cache = TypeCompatibilityCache()
    return _global_compatibility_cache


class SymbolTypeCache:
    """Cache for symbol-to-type mappings.
    
    Provides fast lookup of types associated with symbols,
    avoiding repeated symbol table traversals.
    """
    
    def __init__(self) -> None:
        """Initialize the symbol type cache."""
        self._symbol_types: WeakValueDictionary[int, JacType] = WeakValueDictionary()
        
    def get_symbol_type(self, symbol_id: int) -> Optional[JacType]:
        """Get the type for a symbol by ID."""
        return self._symbol_types.get(symbol_id)
        
    def set_symbol_type(self, symbol_id: int, type_instance: JacType) -> None:
        """Set the type for a symbol."""
        self._symbol_types[symbol_id] = type_instance
        
    def clear_symbol(self, symbol_id: int) -> None:
        """Clear the type for a specific symbol."""
        self._symbol_types.pop(symbol_id, None)
        
    def clear(self) -> None:
        """Clear all symbol type mappings."""
        self._symbol_types.clear()
        
    def size(self) -> int:
        """Get the current cache size."""
        return len(self._symbol_types)


# Global symbol type cache
_global_symbol_cache: Optional[SymbolTypeCache] = None


def get_global_symbol_cache() -> SymbolTypeCache:
    """Get the global symbol type cache."""
    global _global_symbol_cache
    if _global_symbol_cache is None:
        _global_symbol_cache = SymbolTypeCache()
    return _global_symbol_cache


def clear_all_caches() -> None:
    """Clear all global caches."""
    global _global_cache, _global_intern_pool, _global_compatibility_cache, _global_symbol_cache
    
    if _global_cache:
        _global_cache.clear()
    if _global_intern_pool:
        _global_intern_pool.clear()
    if _global_compatibility_cache:
        _global_compatibility_cache.clear()
    if _global_symbol_cache:
        _global_symbol_cache.clear()


def get_all_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches."""
    stats = {}
    
    if _global_cache:
        stats["type_cache"] = _global_cache.get_stats()
    if _global_intern_pool:
        stats["intern_pool_size"] = _global_intern_pool.size()
    if _global_compatibility_cache:
        stats["compatibility_cache_size"] = _global_compatibility_cache.size()
    if _global_symbol_cache:
        stats["symbol_cache_size"] = _global_symbol_cache.size()
        
    return stats
