"""
Phase 5: Performance Optimizer - System optimization and tuning

Optimizes execution performance through caching, batching, and profiling.
Monitors and improves response times and throughput.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics data"""
    task_id: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    cache_hit: bool
    timestamp: float


class PerformanceOptimizer:
    """
    System performance optimizer.
    
    Optimizes:
    - Query caching
    - Batch processing
    - Resource allocation
    - Execution profiling
    - Performance tuning
    """
    
    def __init__(
        self,
        cache_enabled: bool = True,
        batch_size: int = 10,
        max_cache_size: int = 1000
    ):
        """
        Initialize PerformanceOptimizer.
        
        Args:
            cache_enabled: Enable result caching
            batch_size: Batch processing size
            max_cache_size: Maximum cache entries
        """
        self.cache_enabled = cache_enabled
        self.batch_size = batch_size
        self.max_cache_size = max_cache_size
        
        self.query_cache: Dict[str, Any] = {}
        self.metrics: List[PerformanceMetrics] = []
        self.performance_profiles: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        logger.info(
            f"PerformanceOptimizer initialized "
            f"(cache_enabled={cache_enabled}, batch_size={batch_size})"
        )
    
    def optimize_execution(
        self,
        task: str,
        execution_fn: Callable,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Execute task with optimization.
        
        Args:
            task: Task description
            execution_fn: Function to execute
            use_cache: Use caching
        
        Returns:
            Result with optimization metrics
        """
        logger.info(f"\n📈 OPTIMIZED EXECUTION")
        logger.info(f"Task: {task[:60]}...")
        
        # Check cache
        cache_key = self._generate_cache_key(task)
        
        if use_cache and self.cache_enabled:
            cached_result = self._get_cached_result(cache_key)
            
            if cached_result:
                logger.info("✅ Cache hit - returning cached result")
                return {
                    'result': cached_result,
                    'from_cache': True,
                    'execution_time': 0.0
                }
        
        # Execute with profiling
        logger.info("Executing with profiling...")
        start_time = time.time()
        
        result = execution_fn()
        
        execution_time = time.time() - start_time
        logger.info(f"✅ Execution complete - {execution_time:.2f}s")
        
        # Cache result
        if self.cache_enabled and use_cache:
            self._cache_result(cache_key, result)
        
        # Record metrics
        metrics = PerformanceMetrics(
            task_id=cache_key,
            execution_time=execution_time,
            memory_usage=0.0,  # Would measure actual memory
            cpu_usage=0.0,     # Would measure actual CPU
            cache_hit=False,
            timestamp=start_time
        )
        self.metrics.append(metrics)
        
        return {
            'result': result,
            'from_cache': False,
            'execution_time': execution_time,
            'metrics': metrics
        }
    
    def batch_optimize(
        self,
        tasks: List[str],
        execution_fn: Callable
    ) -> List[Dict[str, Any]]:
        """
        Optimize batch execution.
        
        Args:
            tasks: List of tasks
            execution_fn: Execution function
        
        Returns:
            Batch results
        """
        logger.info(f"\n📊 BATCH OPTIMIZATION")
        logger.info(f"Tasks: {len(tasks)}")
        logger.info(f"Batch size: {self.batch_size}")
        
        results = []
        
        # Process in batches
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i:i+self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1}: {len(batch)} tasks")
            
            batch_results = []
            
            for task in batch:
                result = self.optimize_execution(
                    task, lambda t=task: execution_fn(t)
                )
                batch_results.append(result)
            
            results.extend(batch_results)
        
        logger.info(f"✅ Batch processing complete - {len(results)} results")
        
        return results
    
    def _generate_cache_key(self, task: str) -> str:
        """Generate cache key from task"""
        import hashlib
        return hashlib.md5(task.encode()).hexdigest()[:16]
    
    def _get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result if available"""
        return self.query_cache.get(key)
    
    def _cache_result(self, key: str, result: Any) -> None:
        """Cache result"""
        # Simple FIFO eviction if cache full
        if len(self.query_cache) >= self.max_cache_size:
            first_key = next(iter(self.query_cache))
            del self.query_cache[first_key]
        
        self.query_cache[key] = result
        logger.debug(f"Cached result for {key}")
    
    def profile_task(
        self,
        task_id: str,
        metrics: Dict[str, float]
    ) -> None:
        """
        Record performance profile for task.
        
        Args:
            task_id: Task identifier
            metrics: Performance metrics
        """
        self.performance_profiles[task_id] = metrics
        logger.debug(f"Profiled task {task_id}: {metrics}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.metrics:
            return {'metrics_count': 0}
        
        execution_times = [m.execution_time for m in self.metrics]
        cache_hits = sum(1 for m in self.metrics if m.cache_hit)
        
        return {
            'total_executions': len(self.metrics),
            'cache_hits': cache_hits,
            'cache_hit_rate': cache_hits / len(self.metrics) if self.metrics else 0,
            'avg_execution_time': sum(execution_times) / len(execution_times) if execution_times else 0,
            'min_execution_time': min(execution_times) if execution_times else 0,
            'max_execution_time': max(execution_times) if execution_times else 0,
            'cache_size': len(self.query_cache)
        }
    
    def optimize_allocation(self) -> Dict[str, Any]:
        """Optimize resource allocation based on metrics"""
        logger.info("\n🔧 RESOURCE ALLOCATION OPTIMIZATION")
        
        summary = self.get_performance_summary()
        
        # Analyze metrics and recommend optimizations
        recommendations = []
        
        if summary.get('cache_hit_rate', 0) < 0.3:
            recommendations.append("Increase batch size for better cache utilization")
        
        avg_time = summary.get('avg_execution_time', 0)
        if avg_time > 5.0:
            recommendations.append("Consider parallel processing for long-running tasks")
        
        if summary.get('cache_size', 0) > self.max_cache_size * 0.8:
            recommendations.append("Cache is near capacity - consider cleanup")
        
        logger.info(f"Recommendations: {len(recommendations)}")
        for rec in recommendations:
            logger.info(f"  • {rec}")
        
        return {
            'summary': summary,
            'recommendations': recommendations
        }
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear the cache"""
        cache_size = len(self.query_cache)
        self.query_cache.clear()
        
        logger.info(f"✅ Cache cleared - {cache_size} entries removed")
        
        return {'cleared_entries': cache_size}
