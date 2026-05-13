"""
Phase 5: Monitoring System - Comprehensive system monitoring and alerting

Monitors system health, performance, and generates alerts.
Tracks metrics, logs, and provides dashboards.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class SystemMetric:
    """System metric data point"""
    metric_name: str
    value: float
    timestamp: float
    tags: Dict[str, str]


@dataclass
class Alert:
    """Alert/notification"""
    id: str
    severity: AlertSeverity
    message: str
    timestamp: float
    resolved: bool = False


class MonitoringSystem:
    """
    Comprehensive system monitoring.
    
    Monitors:
    - System health
    - Performance metrics
    - Error rates
    - Resource usage
    - API availability
    """
    
    def __init__(
        self,
        alert_thresholds: Optional[Dict[str, float]] = None,
        retention_hours: int = 24
    ):
        """
        Initialize MonitoringSystem.
        
        Args:
            alert_thresholds: Thresholds for alerts
            retention_hours: Metrics retention period
        """
        self.alert_thresholds = alert_thresholds or {
            'error_rate': 0.1,      # 10%
            'response_time': 5.0,   # 5 seconds
            'cpu_usage': 80.0,      # 80%
            'memory_usage': 85.0    # 85%
        }
        self.retention_hours = retention_hours
        
        self.metrics: List[SystemMetric] = []
        self.alerts: List[Alert] = []
        self.health_checks: Dict[str, bool] = {}
        self.service_status: Dict[str, str] = {}
        
        logger.info("MonitoringSystem initialized")
    
    def record_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record system metric.
        
        Args:
            metric_name: Name of metric
            value: Metric value
            tags: Optional tags
        """
        metric = SystemMetric(
            metric_name=metric_name,
            value=value,
            timestamp=time.time(),
            tags=tags or {}
        )
        
        self.metrics.append(metric)
        
        # Check thresholds
        if metric_name in self.alert_thresholds:
            if value > self.alert_thresholds[metric_name]:
                self._create_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"{metric_name} exceeded threshold: {value:.2f}"
                )
        
        logger.debug(f"Recorded {metric_name}: {value}")
    
    def check_health(
        self,
        component: str,
        is_healthy: bool
    ) -> None:
        """
        Record health check result.
        
        Args:
            component: Component name
            is_healthy: Health status
        """
        self.health_checks[component] = is_healthy
        status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
        logger.info(f"Health check {component}: {status}")
        
        if not is_healthy:
            self._create_alert(
                severity=AlertSeverity.CRITICAL,
                message=f"Component {component} is unhealthy"
            )
    
    def set_service_status(self, service: str, status: str) -> None:
        """
        Set service status.
        
        Args:
            service: Service name
            status: Status value (running, stopped, error)
        """
        self.service_status[service] = status
        logger.info(f"Service {service}: {status}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        logger.info("\n📊 SYSTEM STATUS")
        
        healthy_components = sum(
            1 for h in self.health_checks.values() if h
        )
        total_components = len(self.health_checks)
        
        running_services = sum(
            1 for s in self.service_status.values()
            if s == "running"
        )
        total_services = len(self.service_status)
        
        active_alerts = sum(
            1 for a in self.alerts if not a.resolved
        )
        
        status = "🟢 Operational" if active_alerts == 0 else "🟡 Degraded"
        
        logger.info(f"Overall Status: {status}")
        logger.info(f"Components: {healthy_components}/{total_components} healthy")
        logger.info(f"Services: {running_services}/{total_services} running")
        logger.info(f"Active Alerts: {active_alerts}")
        
        return {
            'overall_status': status,
            'components_healthy': healthy_components,
            'components_total': total_components,
            'services_running': running_services,
            'services_total': total_services,
            'active_alerts': active_alerts,
            'component_status': self.health_checks,
            'service_status': self.service_status
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics summary"""
        if not self.metrics:
            return {'metrics_count': 0}
        
        # Group by metric name
        metrics_by_name = defaultdict(list)
        
        for metric in self.metrics:
            metrics_by_name[metric.metric_name].append(metric.value)
        
        summary = {}
        
        for metric_name, values in metrics_by_name.items():
            summary[metric_name] = {
                'current': values[-1] if values else 0,
                'avg': sum(values) / len(values) if values else 0,
                'min': min(values) if values else 0,
                'max': max(values) if values else 0,
                'count': len(values)
            }
        
        logger.info("📈 Performance Metrics:")
        for name, stats in summary.items():
            logger.info(f"  {name}: avg={stats['avg']:.2f}, current={stats['current']:.2f}")
        
        return summary
    
    def get_alerts(
        self,
        unresolved_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get alerts.
        
        Args:
            unresolved_only: Only return unresolved alerts
        
        Returns:
            List of alerts
        """
        alerts = self.alerts
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        return [asdict(a) for a in alerts]
    
    def resolve_alert(self, alert_id: str) -> None:
        """Resolve an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                logger.info(f"✅ Alert resolved: {alert_id}")
                return
        
        logger.warning(f"Alert not found: {alert_id}")
    
    def _create_alert(
        self,
        severity: AlertSeverity,
        message: str
    ) -> None:
        """Create new alert"""
        alert_id = f"alert_{int(time.time() * 1000)}"
        
        alert = Alert(
            id=alert_id,
            severity=severity,
            message=message,
            timestamp=time.time()
        )
        
        self.alerts.append(alert)
        
        logger.warning(
            f"🚨 [{severity.value.upper()}] {message}"
        )
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate monitoring report"""
        logger.info("\n📋 MONITORING REPORT")
        
        system_status = self.get_system_status()
        performance = self.get_performance_metrics()
        active_alerts = self.get_alerts(unresolved_only=True)
        
        report = {
            'timestamp': time.time(),
            'system_status': system_status,
            'performance_metrics': performance,
            'alerts': active_alerts,
            'total_metrics_recorded': len(self.metrics),
            'total_alerts_created': len(self.alerts)
        }
        
        logger.info(f"Report generated with {len(active_alerts)} active alerts")
        
        return report
    
    def cleanup_old_metrics(self) -> Dict[str, int]:
        """Remove old metrics beyond retention period"""
        cutoff_time = time.time() - (self.retention_hours * 3600)
        
        initial_count = len(self.metrics)
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]
        removed_count = initial_count - len(self.metrics)
        
        logger.info(f"✅ Cleaned up {removed_count} old metrics")
        
        return {'removed': removed_count, 'remaining': len(self.metrics)}
