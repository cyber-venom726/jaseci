"""Memory management system for JacAgent framework."""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from jacagent.exceptions import MemoryError
from jacagent.plugins.hooks import get_hook_manager
from jacagent.config import get_config, MemoryBackend


class MemoryType(str, Enum):
    """Types of memory storage."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"


class MemoryItem(BaseModel):
    """A single memory item."""
    key: str
    value: Any
    memory_type: MemoryType
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expiry: Optional[datetime] = None
    access_count: int = Field(default=0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MemoryQuery(BaseModel):
    """Query for memory retrieval."""
    key: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    tags: List[str] = Field(default_factory=list)
    time_range: Optional[tuple] = None
    importance_threshold: float = Field(default=0.0)
    limit: int = Field(default=10, gt=0)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class BaseMemoryBackend(ABC):
    """Base class for memory storage backends."""
    
    @abstractmethod
    async def store(self, item: MemoryItem) -> None:
        """Store a memory item."""
        pass
    
    @abstractmethod
    async def retrieve(self, key: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by key."""
        pass
    
    @abstractmethod
    async def search(self, query: MemoryQuery) -> List[MemoryItem]:
        """Search for memory items."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a memory item."""
        pass
    
    @abstractmethod
    async def clear(self, memory_type: Optional[MemoryType] = None) -> int:
        """Clear memory items."""
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired memory items."""
        pass


class LocalMemoryBackend(BaseMemoryBackend):
    """Local in-memory storage backend."""
    
    def __init__(self):
        self._storage: Dict[str, MemoryItem] = {}
        self._indexes: Dict[MemoryType, List[str]] = {
            memory_type: [] for memory_type in MemoryType
        }
    
    async def store(self, item: MemoryItem) -> None:
        """Store a memory item."""
        self._storage[item.key] = item
        
        # Update indexes
        if item.key not in self._indexes[item.memory_type]:
            self._indexes[item.memory_type].append(item.key)
    
    async def retrieve(self, key: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by key."""
        item = self._storage.get(key)
        if item:
            # Update access count
            item.access_count += 1
            self._storage[key] = item
        return item
    
    async def search(self, query: MemoryQuery) -> List[MemoryItem]:
        """Search for memory items."""
        results = []
        
        # Filter by memory type
        keys_to_search = []
        if query.memory_type:
            keys_to_search = self._indexes[query.memory_type]
        else:
            keys_to_search = list(self._storage.keys())
        
        for key in keys_to_search:
            item = self._storage.get(key)
            if not item:
                continue
            
            # Apply filters
            if query.key and query.key != item.key:
                continue
            
            if query.importance_threshold > item.importance:
                continue
            
            if query.time_range:
                start_time, end_time = query.time_range
                if not (start_time <= item.timestamp <= end_time):
                    continue
            
            if query.tags:
                item_tags = item.metadata.get("tags", [])
                if not any(tag in item_tags for tag in query.tags):
                    continue
            
            results.append(item)
        
        # Sort by importance and timestamp
        results.sort(key=lambda x: (x.importance, x.timestamp), reverse=True)
        
        return results[:query.limit]
    
    async def delete(self, key: str) -> bool:
        """Delete a memory item."""
        if key in self._storage:
            item = self._storage[key]
            del self._storage[key]
            
            # Update indexes
            if key in self._indexes[item.memory_type]:
                self._indexes[item.memory_type].remove(key)
            
            return True
        return False
    
    async def clear(self, memory_type: Optional[MemoryType] = None) -> int:
        """Clear memory items."""
        if memory_type:
            keys_to_delete = self._indexes[memory_type].copy()
            count = 0
            for key in keys_to_delete:
                if await self.delete(key):
                    count += 1
            return count
        else:
            count = len(self._storage)
            self._storage.clear()
            for memory_type in MemoryType:
                self._indexes[memory_type].clear()
            return count
    
    async def cleanup_expired(self) -> int:
        """Clean up expired memory items."""
        now = datetime.now()
        expired_keys = []
        
        for key, item in self._storage.items():
            if item.expiry and item.expiry <= now:
                expired_keys.append(key)
        
        count = 0
        for key in expired_keys:
            if await self.delete(key):
                count += 1
        
        return count


class RedisMemoryBackend(BaseMemoryBackend):
    """Redis-based memory storage backend."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._redis = None
    
    async def _get_redis(self):
        """Get Redis connection."""
        if not self._redis:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.connection_string)
        return self._redis
    
    async def store(self, item: MemoryItem) -> None:
        """Store a memory item."""
        redis = await self._get_redis()
        
        # Serialize item
        data = item.json()
        
        # Store with expiry if specified
        if item.expiry:
            expiry_seconds = int((item.expiry - datetime.now()).total_seconds())
            await redis.setex(f"memory:{item.key}", expiry_seconds, data)
        else:
            await redis.set(f"memory:{item.key}", data)
        
        # Add to type index
        await redis.sadd(f"type_index:{item.memory_type.value}", item.key)
    
    async def retrieve(self, key: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by key."""
        redis = await self._get_redis()
        
        data = await redis.get(f"memory:{key}")
        if not data:
            return None
        
        item = MemoryItem.parse_raw(data)
        
        # Update access count
        item.access_count += 1
        await self.store(item)
        
        return item
    
    async def search(self, query: MemoryQuery) -> List[MemoryItem]:
        """Search for memory items."""
        redis = await self._get_redis()
        results = []
        
        # Get keys to search
        if query.memory_type:
            keys = await redis.smembers(f"type_index:{query.memory_type.value}")
        else:
            keys = await redis.keys("memory:*")
            keys = [key.decode().replace("memory:", "") for key in keys]
        
        # Retrieve and filter items
        for key in keys:
            item = await self.retrieve(key)
            if not item:
                continue
            
            # Apply filters (similar to LocalMemoryBackend)
            if query.key and query.key != item.key:
                continue
            
            if query.importance_threshold > item.importance:
                continue
            
            results.append(item)
        
        # Sort and limit
        results.sort(key=lambda x: (x.importance, x.timestamp), reverse=True)
        return results[:query.limit]
    
    async def delete(self, key: str) -> bool:
        """Delete a memory item."""
        redis = await self._get_redis()
        
        # Get item to find its type
        item = await self.retrieve(key)
        if not item:
            return False
        
        # Delete from storage and index
        deleted = await redis.delete(f"memory:{key}")
        await redis.srem(f"type_index:{item.memory_type.value}", key)
        
        return deleted > 0
    
    async def clear(self, memory_type: Optional[MemoryType] = None) -> int:
        """Clear memory items."""
        redis = await self._get_redis()
        
        if memory_type:
            keys = await redis.smembers(f"type_index:{memory_type.value}")
            count = 0
            for key in keys:
                if await self.delete(key):
                    count += 1
            return count
        else:
            keys = await redis.keys("memory:*")
            if keys:
                await redis.delete(*keys)
            
            # Clear indexes
            for memory_type in MemoryType:
                await redis.delete(f"type_index:{memory_type.value}")
            
            return len(keys)
    
    async def cleanup_expired(self) -> int:
        """Clean up expired memory items."""
        # Redis handles TTL automatically
        return 0


class MemoryManager:
    """High-level memory management interface."""
    
    def __init__(self, backend: Optional[BaseMemoryBackend] = None):
        self._backend = backend or self._create_default_backend()
        self._hook_manager = get_hook_manager()
    
    def _create_default_backend(self) -> BaseMemoryBackend:
        """Create default memory backend based on configuration."""
        config = get_config()
        
        if config.memory.backend == MemoryBackend.LOCAL:
            return LocalMemoryBackend()
        elif config.memory.backend == MemoryBackend.REDIS:
            if not config.memory.connection_string:
                raise MemoryError("Redis connection string required")
            return RedisMemoryBackend(config.memory.connection_string)
        else:
            raise MemoryError(f"Unsupported memory backend: {config.memory.backend}")
    
    async def store(
        self, 
        key: str, 
        value: Any, 
        memory_type: MemoryType = MemoryType.WORKING,
        importance: float = 0.5,
        expiry: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a value in memory."""
        context = context or {}
        
        # Before hook
        hook_results = await self._hook_manager.call_hook(
            "before_memory_store",
            key=key,
            value=value,
            context=context
        )
        
        # Apply hook transformations
        for result in hook_results:
            if isinstance(result, tuple) and len(result) == 2:
                key, value = result
        
        # Create memory item
        item = MemoryItem(
            key=key,
            value=value,
            memory_type=memory_type,
            importance=importance,
            expiry=expiry,
            metadata=metadata or {}
        )
        
        # Store in backend
        await self._backend.store(item)
        
        # After hook
        await self._hook_manager.call_hook(
            "after_memory_store",
            key=key,
            value=value,
            context=context
        )
    
    async def retrieve(
        self, 
        key: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Retrieve a value from memory."""
        context = context or {}
        
        # Before hook
        hook_results = await self._hook_manager.call_hook(
            "before_memory_retrieve",
            key=key,
            context=context
        )
        
        # Apply hook transformations
        for result in hook_results:
            if isinstance(result, str):
                key = result
        
        # Retrieve from backend
        item = await self._backend.retrieve(key)
        value = item.value if item else None
        
        # After hook
        hook_results = await self._hook_manager.call_hook(
            "after_memory_retrieve",
            key=key,
            value=value,
            context=context
        )
        
        # Apply hook transformations
        for result in hook_results:
            if result is not None:
                value = result
        
        return value
    
    async def search(self, query: MemoryQuery) -> List[MemoryItem]:
        """Search for memory items."""
        return await self._backend.search(query)
    
    async def delete(self, key: str) -> bool:
        """Delete a memory item."""
        return await self._backend.delete(key)
    
    async def clear(self, memory_type: Optional[MemoryType] = None) -> int:
        """Clear memory items."""
        return await self._backend.clear(memory_type)
    
    async def cleanup_expired(self) -> int:
        """Clean up expired memory items."""
        return await self._backend.cleanup_expired()
    
    # Convenience methods for different memory types
    async def store_short_term(self, key: str, value: Any, **kwargs) -> None:
        """Store in short-term memory."""
        await self.store(key, value, MemoryType.SHORT_TERM, **kwargs)
    
    async def store_long_term(self, key: str, value: Any, **kwargs) -> None:
        """Store in long-term memory."""
        await self.store(key, value, MemoryType.LONG_TERM, **kwargs)
    
    async def store_episodic(self, key: str, value: Any, **kwargs) -> None:
        """Store episodic memory."""
        await self.store(key, value, MemoryType.EPISODIC, **kwargs)
    
    async def store_semantic(self, key: str, value: Any, **kwargs) -> None:
        """Store semantic memory."""
        await self.store(key, value, MemoryType.SEMANTIC, **kwargs)
    
    async def get_recent_memories(self, memory_type: MemoryType, limit: int = 10) -> List[MemoryItem]:
        """Get recent memories of a specific type."""
        query = MemoryQuery(memory_type=memory_type, limit=limit)
        return await self.search(query)


# Global memory manager instance
_global_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager()
    return _global_memory_manager
