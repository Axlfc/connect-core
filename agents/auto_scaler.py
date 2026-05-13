"""
Phase 5: Auto Scaler - Automatic scaling and resource management

Automatically scales services based on demand and metrics.
Implements multiple scaling strategies and policies.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ScalingPolicy(Enum):
    """Scaling policies"""
    CPU_BASED = "cpu_based"
    MEMORY_BASED = "memory_based"
    REQUEST_BASED = "request_based"
    CUSTOM = "custom"


class ScalingDirection(Enum):
    """Scaling direction"""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


@dataclass
class ScalingMetrics:
    """Metrics for scaling decision"""
    current_replicas: int
    avg_cpu: float
    avg_memory: float
    request_rate: float
    response_time: float
    error_rate: float


class AutoScaler:
    """
    Automatic service scaling system.
    
    Features:
    - Multiple scaling policies
    - Configurable thresholds
    - Cooldown periods
    - Scaling history
    """
    
    def __init__(
        self,
        min_replicas: int = 1,
        max_replicas: int = 10,
        scaling_policy: ScalingPolicy = ScalingPolicy.REQUEST_BASED,
        cooldown_seconds: int = 60
    ):
        """
        Initialize AutoScaler.
        
        Args:
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            scaling_policy: Scaling policy to use
            cooldown_seconds: Cooldown between scaling events
        """
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.scaling_policy = scaling_policy
        self.cooldown_seconds = cooldown_seconds
        
        self.current_replicas = min_replicas
        self.last_scaling_time = 0
        self.scaling_history: List[Dict[str, Any]] = []
        
        # Scaling thresholds
        self.scale_up_threshold = {
            ScalingPolicy.CPU_BASED: 75.0,      # 75% CPU
            ScalingPolicy.MEMORY_BASED: 80.0,    # 80% Memory
            ScalingPolicy.REQUEST_BASED: 100.0   # 100 req/s
        }
        
        self.scale_down_threshold = {
            ScalingPolicy.CPU_BASED: 25.0,       # 25% CPU
            ScalingPolicy.MEMORY_BASED: 30.0,    # 30% Memory
            ScalingPolicy.REQUEST_BASED: 20.0    # 20 req/s
        }
        
        logger.info(
            f"AutoScaler initialized "
            f"(min={min_replicas}, max={max_replicas}, policy={scaling_policy.value})"
        )
    
    def evaluate_scaling(self, metrics: ScalingMetrics) -> Optional[int]:
        """
        Evaluate if scaling is needed.
        
        Args:
            metrics: Current system metrics
        
        Returns:
            Target replica count or None if no scaling needed
        """
        logger.info(f"\n🔄 SCALING EVALUATION")
        logger.info(f"Current replicas: {self.current_replicas}")
        logger.info(f"Policy: {self.scaling_policy.value}")
        
        # Check cooldown
        if time.time() - self.last_scaling_time < self.cooldown_seconds:
            logger.info(f"⏳ Cooldown active - no scaling")
            return None
        
        # Decide scaling direction
        direction = self._determine_scaling_direction(metrics)
        
        if direction == ScalingDirection.STABLE:
            logger.info("✅ System stable - no scaling needed")
            return None
        
        # Calculate target replicas
        target = self._calculate_target_replicas(metrics, direction)
        
        if target == self.current_replicas:
            logger.info("✅ No replica change needed")
            return None
        
        # Perform scaling
        return self._perform_scaling(target)
    
    def _determine_scaling_direction(
        self,
        metrics: ScalingMetrics
    ) -> ScalingDirection:
        """Determine if we should scale up, down, or stay stable"""
        
        if self.scaling_policy == ScalingPolicy.CPU_BASED:
            threshold_up = self.scale_up_threshold[ScalingPolicy.CPU_BASED]
            threshold_down = self.scale_down_threshold[ScalingPolicy.CPU_BASED]
            metric_value = metrics.avg_cpu
            
        elif self.scaling_policy == ScalingPolicy.MEMORY_BASED:
            threshold_up = self.scale_up_threshold[ScalingPolicy.MEMORY_BASED]
            threshold_down = self.scale_down_threshold[ScalingPolicy.MEMORY_BASED]
            metric_value = metrics.avg_memory
            
        else:  # REQUEST_BASED
            threshold_up = self.scale_up_threshold[ScalingPolicy.REQUEST_BASED]
            threshold_down = self.scale_down_threshold[ScalingPolicy.REQUEST_BASED]
            metric_value = metrics.request_rate
        
        logger.info(
            f"Metric: {metric_value:.1f} "
            f"(scale_up: {threshold_up}, scale_down: {threshold_down})"
        )
        
        if metric_value > threshold_up:
            logger.info("📈 Scale UP indicated")
            return ScalingDirection.UP
        
        elif metric_value < threshold_down:
            logger.info("📉 Scale DOWN indicated")
            return ScalingDirection.DOWN
        
        else:
            logger.info("➡️ Stable")
            return ScalingDirection.STABLE
    
    def _calculate_target_replicas(
        self,
        metrics: ScalingMetrics,
        direction: ScalingDirection
    ) -> int:
        """Calculate target number of replicas"""
        
        if direction == ScalingDirection.UP:
            # Increase by 1 or 2 replicas
            increase = 2 if metrics.avg_cpu > 90 else 1
            target = min(
                self.current_replicas + increase,
                self.max_replicas
            )
            logger.info(f"Calculated target (UP): {self.current_replicas} → {target}")
            return target
        
        elif direction == ScalingDirection.DOWN:
            # Decrease by 1 replica
            target = max(
                self.current_replicas - 1,
                self.min_replicas
            )
            logger.info(f"Calculated target (DOWN): {self.current_replicas} → {target}")
            return target
        
        else:
            return self.current_replicas
    
    def _perform_scaling(self, target_replicas: int) -> int:
        """Perform the actual scaling"""
        direction = "UP" if target_replicas > self.current_replicas else "DOWN"
        delta = abs(target_replicas - self.current_replicas)
        
        logger.info(f"🔄 Scaling {direction} by {delta} replicas")
        logger.info(f"{self.current_replicas} → {target_replicas}")
        
        # Record in history
        self.scaling_history.append({
            'timestamp': time.time(),
            'from': self.current_replicas,
            'to': target_replicas,
            'direction': direction,
            'policy': self.scaling_policy.value
        })
        
        # Update current replicas
        self.current_replicas = target_replicas
        self.last_scaling_time = time.time()
        
        logger.info(f"✅ Scaling complete - {target_replicas} replicas active")
        
        return target_replicas
    
    def set_scaling_threshold(
        self,
        policy: ScalingPolicy,
        up_threshold: float,
        down_threshold: float
    ) -> None:
        """
        Set custom scaling thresholds.
        
        Args:
            policy: Scaling policy
            up_threshold: Scale up threshold
            down_threshold: Scale down threshold
        """
        self.scale_up_threshold[policy] = up_threshold
        self.scale_down_threshold[policy] = down_threshold
        
        logger.info(
            f"✅ Updated thresholds for {policy.value}: "
            f"up={up_threshold}, down={down_threshold}"
        )
    
    def get_scaling_status(self) -> Dict[str, Any]:
        """Get scaling system status"""
        return {
            'current_replicas': self.current_replicas,
            'min_replicas': self.min_replicas,
            'max_replicas': self.max_replicas,
            'scaling_policy': self.scaling_policy.value,
            'last_scaling_time': self.last_scaling_time,
            'scaling_events': len(self.scaling_history)
        }
    
    def get_scaling_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get scaling history.
        
        Args:
            limit: Maximum number of history entries to return
        
        Returns:
            Scaling history
        """
        history = self.scaling_history
        
        if limit:
            history = history[-limit:]
        
        logger.info(f"Scaling history: {len(history)} events")
        
        return history
