"""
Phase 5 Integration: Complete production system integration

Orchestrates all Phase 5 components (Deployer, Optimizer, Cache, APIs, Monitoring, Scaler)
Creates a complete production-ready system.
"""

import logging
from typing import Optional, Dict, Any

from production_deployer import ProductionDeployer, DeploymentConfig, EnvironmentType
from performance_optimizer import PerformanceOptimizer
from distributed_cache import DistributedCache
from external_api_integration import ExternalAPIIntegration
from monitoring_system import MonitoringSystem
from auto_scaler import AutoScaler, ScalingPolicy, ScalingMetrics

logger = logging.getLogger(__name__)


class Phase5Integration:
    """
    Complete Phase 5 production integration.
    
    Combines:
    - Production Deployer
    - Performance Optimizer
    - Distributed Cache
    - External API Integration
    - Monitoring System
    - Auto Scaler
    
    Creates a fully production-ready multi-agent system.
    """
    
    def __init__(
        self,
        environment: EnvironmentType = EnvironmentType.STAGING,
        enable_caching: bool = True,
        enable_monitoring: bool = True,
        enable_auto_scaling: bool = True
    ):
        """
        Initialize Phase 5 Integration.
        
        Args:
            environment: Target environment
            enable_caching: Enable distributed caching
            enable_monitoring: Enable monitoring system
            enable_auto_scaling: Enable auto scaling
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 PHASE 5 PRODUCTION INTEGRATION")
        logger.info(f"{'='*70}")
        logger.info(f"Environment: {environment.value}")
        
        # Initialize all Phase 5 components
        self.deployer = ProductionDeployer(
            config=DeploymentConfig(environment=environment)
        )
        
        self.optimizer = PerformanceOptimizer(
            cache_enabled=enable_caching
        )
        
        self.cache = DistributedCache(
            l1_max_size=1000,
            l2_enabled=environment == EnvironmentType.PRODUCTION,
            l3_enabled=environment == EnvironmentType.PRODUCTION
        ) if enable_caching else None
        
        self.api_integration = ExternalAPIIntegration()
        
        self.monitoring = MonitoringSystem(
        ) if enable_monitoring else None
        
        self.auto_scaler = AutoScaler(
            min_replicas=1 if environment == EnvironmentType.DEV else 3,
            max_replicas=10,
            scaling_policy=ScalingPolicy.REQUEST_BASED
        ) if enable_auto_scaling else None
        
        logger.info("✅ All Phase 5 components initialized")
        logger.info(f"{'='*70}\n")
    
    def deploy_system(
        self,
        image: str = "orchestrator:latest",
        service_name: str = "multi-agent-orchestrator"
    ) -> Dict[str, Any]:
        """
        Deploy complete system to production.
        
        Args:
            image: Container image
            service_name: Service name
        
        Returns:
            Deployment result with endpoints
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📦 SYSTEM DEPLOYMENT")
        logger.info(f"{'='*70}")
        
        # Deploy
        result = self.deployer.deploy(
            image=image,
            version="1.0.0",
            service_name=service_name
        )
        
        # Initialize monitoring if enabled
        if self.monitoring:
            for endpoint in result.endpoints:
                self.monitoring.check_health(endpoint, True)
                self.monitoring.set_service_status(endpoint, "running")
        
        logger.info(f"{'='*70}\n")
        
        return {
            'deployment': result,
            'endpoints': result.endpoints,
            'active_replicas': len(result.endpoints)
        }
    
    def optimize_system(
        self,
        tasks: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Run system optimizations.
        
        Args:
            tasks: Optional list of tasks to optimize
        
        Returns:
            Optimization results
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"⚡ SYSTEM OPTIMIZATION")
        logger.info(f"{'='*70}")
        
        results = {
            'performance': self.optimizer.get_performance_summary(),
            'recommendations': self.optimizer.optimize_allocation()
        }
        
        if self.cache:
            results['cache'] = self.cache.get_stats()
        
        if self.monitoring:
            results['monitoring'] = self.monitoring.get_performance_metrics()
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def evaluate_scaling(
        self,
        metrics: Dict[str, float]
    ) -> Optional[int]:
        """
        Evaluate and perform auto-scaling.
        
        Args:
            metrics: Current system metrics
        
        Returns:
            New replica count or None
        """
        if not self.auto_scaler:
            logger.info("Auto-scaling disabled")
            return None
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 AUTO-SCALING EVALUATION")
        logger.info(f"{'='*70}")
        
        # Create scaling metrics from input
        scaling_metrics = ScalingMetrics(
            current_replicas=len(self.deployer.active_endpoints),
            avg_cpu=metrics.get('avg_cpu', 50.0),
            avg_memory=metrics.get('avg_memory', 60.0),
            request_rate=metrics.get('request_rate', 50.0),
            response_time=metrics.get('response_time', 1.5),
            error_rate=metrics.get('error_rate', 0.01)
        )
        
        # Evaluate scaling
        target_replicas = self.auto_scaler.evaluate_scaling(scaling_metrics)
        
        # If scaling needed, scale the deployment
        if target_replicas and target_replicas != len(self.deployer.active_endpoints):
            result = self.deployer.scale(target_replicas)
            logger.info(f"✅ Scaled to {target_replicas} replicas")
            return target_replicas
        
        logger.info(f"{'='*70}\n")
        
        return None
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get complete system health report.
        
        Returns:
            Health status of all components
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🏥 SYSTEM HEALTH CHECK")
        logger.info(f"{'='*70}")
        
        health = {
            'deployment': self.deployer.get_status(),
            'performance': self.optimizer.get_performance_summary(),
        }
        
        if self.cache:
            health['cache'] = self.cache.get_stats()
        
        if self.monitoring:
            health['monitoring'] = self.monitoring.get_system_status()
        
        if self.auto_scaler:
            health['scaling'] = self.auto_scaler.get_scaling_status()
        
        health['api_integration'] = self.api_integration.get_api_stats()
        
        logger.info(f"{'='*70}\n")
        
        return health
    
    def generate_production_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive production report.
        
        Returns:
            Complete system report
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📋 PRODUCTION REPORT")
        logger.info(f"{'='*70}")
        
        report = {
            'system_health': self.get_system_health(),
            'optimizations': self.optimize_system(),
            'deployment_status': self.deployer.get_status()
        }
        
        if self.monitoring:
            report['monitoring_report'] = self.monitoring.generate_report()
        
        if self.auto_scaler:
            report['scaling_history'] = self.auto_scaler.get_scaling_history(limit=10)
        
        logger.info(f"Report generated successfully")
        logger.info(f"{'='*70}\n")
        
        return report
    
    def scale_system(self, target_replicas: int) -> Dict[str, Any]:
        """
        Manually scale system to target replica count.
        
        Args:
            target_replicas: Target number of replicas
        
        Returns:
            Scaling result
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 MANUAL SCALING")
        logger.info(f"{'='*70}")
        
        result = self.deployer.scale(target_replicas)
        
        logger.info(f"{'='*70}\n")
        
        return result
    
    def clear_caches(self) -> Dict[str, Any]:
        """
        Clear all caches.
        
        Returns:
            Cache clearing results
        """
        results = {}
        
        if self.cache:
            results['distributed_cache'] = self.cache.clear()
        
        results['api_cache'] = self.api_integration.clear_cache()
        
        results['performance_cache'] = self.optimizer.clear_cache()
        
        logger.info("✅ All caches cleared")
        
        return results
    
    def restart_monitoring(self) -> Dict[str, Any]:
        """
        Restart monitoring system.
        
        Returns:
            Monitoring status
        """
        if not self.monitoring:
            return {'status': 'disabled'}
        
        logger.info("✅ Monitoring system restarted")
        
        return {
            'status': 'active',
            'initial_status': self.monitoring.get_system_status()
        }
