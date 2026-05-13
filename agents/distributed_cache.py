"""
Phase 5: Distributed Cache - Multi-level caching system

Implements distributed caching for high-performance scenarios.
Supports in-memory, Redis, and persistent storage backends.
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache hierarchy levels"""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_PERSISTENT = "l3_persistent"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    timestamp: float
    ttl: int  # Time to live in seconds
    level: CacheLevel
    hit_count: int = 0


class DistributedCache:
    """
    Distributed multi-level cache system.
    
    Levels:
    - L1: In-memory cache (fast, local)
    - L2: Redis cache (distributed, medium)
    - L3: Persistent storage (slow, reliable)
    """
    
    def __init__(
        self,
        l1_max_size: int = 1000,
        l2_enabled: bool = False,
        l3_enabled: bool = False,
        default_ttl: int = 3600
    ):
        """
        Initialize DistributedCache.
        
        Args:
            l1_max_size: L1 cache max entries
            l2_enabled: Enable L2 Redis cache
            l3_enabled: Enable L3 persistent cache
            default_ttl: Default TTL in seconds
        """
        self.l1_max_size = l1_max_size
        self.l2_enabled = l2_enabled
        self.l3_enabled = l3_enabled
        self.default_ttl = default_ttl
        
        # L1: In-memory store
        self.l1_cache: Dict[str, CacheEntry] = {}
        
        # L2: Redis (simulated)
        self.l2_cache: Dict[str, CacheEntry] = {} if l2_enabled else None
        
        # L3: Persistent storage (simulated)
        self.l3_cache: Dict[str, CacheEntry] = {} if l3_enabled else None
        
        self.stats = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'l3_hits': 0,
            'l3_misses': 0
        }
        
        logger.info(
            f"DistributedCache initialized "
            f"(L1={l1_max_size}, L2={l2_enabled}, L3={l3_enabled})"
        )
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache using multi-level lookup.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        # Try L1 first
        entry = self._get_from_l1(key)
        
        if entry:
            self.stats['l1_hits'] += 1
            logger.debug(f"✅ L1 cache hit: {key}")
            return entry.value
        
        self.stats['l1_misses'] += 1
        
        # Try L2
        if self.l2_enabled:
            entry = self._get_from_l2(key)
            
            if entry:
                self.stats['l2_hits'] += 1
                logger.debug(f"✅ L2 cache hit: {key}")
                # Promote to L1
                self._promote_to_l1(key, entry)
                return entry.value
            
            self.stats['l2_misses'] += 1
        
        # Try L3
        if self.l3_enabled:
            entry = self._get_from_l3(key)
            
            if entry:
                self.stats['l3_hits'] += 1
                logger.debug(f"✅ L3 cache hit: {key}")
                # Promote to L1 and L2
                self._promote_to_l1(key, entry)
                if self.l2_enabled:
                    self._promote_to_l2(key, entry)
                return entry.value
            
            self.stats['l3_misses'] += 1
        
        logger.debug(f"❌ Cache miss: {key}")
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        level: CacheLevel = CacheLevel.L1_MEMORY
    ) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live (uses default if None)
            level: Target cache level
        """
        ttl = ttl or self.default_ttl
        
        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl,
            level=level
        )
        
        # Set in target level
        if level == CacheLevel.L1_MEMORY:
            self._set_l1(key, entry)
        elif level == CacheLevel.L2_REDIS and self.l2_enabled:
            self._set_l2(key, entry)
        elif level == CacheLevel.L3_PERSISTENT and self.l3_enabled:
            self._set_l3(key, entry)
        
        logger.debug(f"Cached in {level.value}: {key}")
    
    def _get_from_l1(self, key: str) -> Optional[CacheEntry]:
        """Get from L1 cache with TTL check"""
        if key not in self.l1_cache:
            return None
        
        entry = self.l1_cache[key]
        
        # Check TTL
        if time.time() - entry.timestamp > entry.ttl:
            del self.l1_cache[key]
            return None
        
        entry.hit_count += 1
        return entry
    
    def _get_from_l2(self, key: str) -> Optional[CacheEntry]:
        """Get from L2 cache"""
        if not self.l2_cache or key not in self.l2_cache:
            return None
        
        entry = self.l2_cache[key]
        
        # Check TTL
        if time.time() - entry.timestamp > entry.ttl:
            del self.l2_cache[key]
            return None
        
        entry.hit_count += 1
        return entry
    
    def _get_from_l3(self, key: str) -> Optional[CacheEntry]:
        """Get from L3 cache"""
        if not self.l3_cache or key not in self.l3_cache:
            return None
        
        entry = self.l3_cache[key]
        
        # Check TTL
        if time.time() - entry.timestamp > entry.ttl:
            del self.l3_cache[key]
            return None
        
        entry.hit_count += 1
        return entry
    
    def _set_l1(self, key: str, entry: CacheEntry) -> None:
        """Set in L1 cache with eviction"""
        if len(self.l1_cache) >= self.l1_max_size:
            # LRU eviction
            oldest_key = min(
                self.l1_cache.keys(),
                key=lambda k: self.l1_cache[k].timestamp
            )
            del self.l1_cache[oldest_key]
        
        self.l1_cache[key] = entry
    
    def _set_l2(self, key: str, entry: CacheEntry) -> None:
        """Set in L2 cache"""
        if self.l2_cache is not None:
            self.l2_cache[key] = entry
    
    def _set_l3(self, key: str, entry: CacheEntry) -> None:
        """Set in L3 cache"""
        if self.l3_cache is not None:
            self.l3_cache[key] = entry
    
    def _promote_to_l1(self, key: str, entry: CacheEntry) -> None:
        """Promote entry from lower level to L1"""
        entry.level = CacheLevel.L1_MEMORY
        self._set_l1(key, entry)
    
    def _promote_to_l2(self, key: str, entry: CacheEntry) -> None:
        """Promote entry to L2"""
        entry.level = CacheLevel.L2_REDIS
        self._set_l2(key, entry)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_hits = sum(
            self.stats[k] for k in self.stats if 'hits' in k
        )
        total_accesses = total_hits + sum(
            self.stats[k] for k in self.stats if 'misses' in k
        )
        
        hit_rate = total_hits / total_accesses if total_accesses > 0 else 0
        
        return {
            'stats': self.stats,
            'total_hits': total_hits,
            'total_accesses': total_accesses,
            'hit_rate': hit_rate,
            'l1_size': len(self.l1_cache),
            'l2_size': len(self.l2_cache) if self.l2_cache else 0,
            'l3_size': len(self.l3_cache) if self.l3_cache else 0
        }
    
    def clear(self, level: Optional[CacheLevel] = None) -> Dict[str, int]:
        """
        Clear cache at specified level or all levels.
        
        Args:
            level: Cache level to clear (None = all)
        
        Returns:
            Cleared entry counts
        """
        cleared = {'l1': 0, 'l2': 0, 'l3': 0}
        
        if level is None or level == CacheLevel.L1_MEMORY:
            cleared['l1'] = len(self.l1_cache)
            self.l1_cache.clear()
        
        if (level is None or level == CacheLevel.L2_REDIS) and self.l2_cache:
            cleared['l2'] = len(self.l2_cache)
            self.l2_cache.clear()
        
        if (level is None or level == CacheLevel.L3_PERSISTENT) and self.l3_cache:
            cleared['l3'] = len(self.l3_cache)
            self.l3_cache.clear()
        
        total_cleared = sum(cleared.values())
        logger.info(f"✅ Cache cleared - {total_cleared} entries")
        
        return cleared
