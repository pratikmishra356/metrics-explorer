"""Utilities for transforming data to OpenTelemetry semantic conventions format."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.metrics import (
    AggregationTemporality,
    Metric,
    MetricDataPoint,
    MetricType,
    ResourceAttributes,
)
from app.models.dashboard import (
    Dashboard,
    DashboardSummary,
    DashboardWidget,
    DashboardWidgetQuery,
    VisualizationType,
    WidgetType,
)
from app.models.monitor import (
    AlertSeverity,
    Monitor,
    MonitorQuery,
    MonitorStatus,
    MonitorSummary,
    MonitorThreshold,
    MonitorType,
)


class OTelTransformer:
    """
    Helper class for transforming provider-specific data to OTel format.
    
    OpenTelemetry Semantic Conventions Reference:
    - Resource: https://opentelemetry.io/docs/specs/semconv/resource/
    - Metrics: https://opentelemetry.io/docs/specs/otel/metrics/data-model/
    """

    @staticmethod
    def create_resource_attributes(
        service_name: Optional[str] = None,
        service_namespace: Optional[str] = None,
        deployment_environment: Optional[str] = None,
        host_name: Optional[str] = None,
        k8s_namespace: Optional[str] = None,
        k8s_pod_name: Optional[str] = None,
        custom: Optional[Dict[str, Any]] = None,
    ) -> ResourceAttributes:
        """Create resource attributes following OTel semantic conventions."""
        return ResourceAttributes(
            service_name=service_name,
            service_namespace=service_namespace,
            deployment_environment=deployment_environment,
            host_name=host_name,
            k8s_namespace_name=k8s_namespace,
            k8s_pod_name=k8s_pod_name,
            custom=custom or {},
        )

    @staticmethod
    def create_metric(
        name: str,
        metric_type: MetricType,
        provider_source: str,
        description: Optional[str] = None,
        unit: Optional[str] = None,
        data_points: Optional[List[MetricDataPoint]] = None,
        resource: Optional[ResourceAttributes] = None,
        aggregation_temporality: Optional[AggregationTemporality] = None,
        is_monotonic: Optional[bool] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> Metric:
        """Create a metric following OTel metric data model."""
        return Metric(
            name=name,
            description=description,
            unit=unit,
            metric_type=metric_type,
            aggregation_temporality=aggregation_temporality,
            is_monotonic=is_monotonic,
            data_points=data_points or [],
            resource=resource or ResourceAttributes(),
            provider_source=provider_source,
            provider_metadata=provider_metadata or {},
        )

    @staticmethod
    def create_data_point(
        time: datetime,
        value: Any,
        attributes: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
    ) -> MetricDataPoint:
        """Create a metric data point."""
        return MetricDataPoint(
            time=time,
            value=value,
            attributes=attributes or {},
            start_time=start_time,
        )

    @staticmethod
    def normalize_metric_name(name: str, provider: str) -> str:
        """
        Normalize metric name to a consistent format.
        
        OTel convention: lowercase with dots as separators.
        Example: system.cpu.utilization
        """
        # Remove provider-specific prefixes
        prefixes_to_remove = [
            "datadog.",
            "prometheus_",
            "grafana_",
        ]
        for prefix in prefixes_to_remove:
            if name.lower().startswith(prefix):
                name = name[len(prefix):]
        
        # Convert to lowercase with dots
        name = name.lower()
        name = name.replace("_", ".")
        name = name.replace("-", ".")
        
        # Remove double dots
        while ".." in name:
            name = name.replace("..", ".")
        
        return name.strip(".")

    @staticmethod
    def normalize_attribute_key(key: str) -> str:
        """
        Normalize attribute key to OTel semantic convention format.
        
        OTel convention: lowercase with dots as namespace separators.
        Example: service.name, deployment.environment
        """
        # Common mappings from provider-specific to OTel conventions
        mappings = {
            # Service attributes
            "service": "service.name",
            "app": "service.name",
            "application": "service.name",
            "env": "deployment.environment",
            "environment": "deployment.environment",
            # Host attributes
            "host": "host.name",
            "hostname": "host.name",
            "instance": "service.instance.id",
            # K8s attributes
            "namespace": "k8s.namespace.name",
            "pod": "k8s.pod.name",
            "pod_name": "k8s.pod.name",
            "deployment": "k8s.deployment.name",
            "container": "container.name",
            # Cloud attributes
            "region": "cloud.region",
            "zone": "cloud.availability_zone",
            "availability_zone": "cloud.availability_zone",
        }
        
        key_lower = key.lower()
        if key_lower in mappings:
            return mappings[key_lower]
        
        # Convert to lowercase with dots
        return key_lower.replace("_", ".").replace("-", ".")

    @staticmethod
    def map_widget_type(provider_type: str, provider: str) -> WidgetType:
        """Map provider-specific widget types to universal widget types."""
        type_lower = provider_type.lower()
        
        # Mapping for common widget types
        mappings = {
            # Timeseries
            "timeseries": WidgetType.TIMESERIES,
            "graph": WidgetType.TIMESERIES,
            "line": WidgetType.TIMESERIES,
            "area": WidgetType.TIMESERIES,
            # Gauge
            "gauge": WidgetType.GAUGE,
            "singlevalue": WidgetType.GAUGE,
            "stat": WidgetType.GAUGE,
            "query_value": WidgetType.GAUGE,
            # Table
            "table": WidgetType.TABLE,
            "query_table": WidgetType.TABLE,
            # Text
            "text": WidgetType.TEXT,
            "note": WidgetType.TEXT,
            "markdown": WidgetType.TEXT,
            # Heatmap
            "heatmap": WidgetType.HEATMAP,
            # Distribution
            "distribution": WidgetType.DISTRIBUTION,
            "histogram": WidgetType.DISTRIBUTION,
            # Top list
            "toplist": WidgetType.TOPLIST,
            "top_list": WidgetType.TOPLIST,
            "bargauge": WidgetType.TOPLIST,
            # Alert
            "alert_graph": WidgetType.ALERT_LIST,
            "alertlist": WidgetType.ALERT_LIST,
            # Log
            "log_stream": WidgetType.LOG_STREAM,
            "logs": WidgetType.LOG_STREAM,
        }
        
        return mappings.get(type_lower, WidgetType.OTHER)

    @staticmethod
    def map_visualization_type(viz_type: str) -> VisualizationType:
        """Map visualization types to universal format."""
        type_lower = viz_type.lower()
        
        mappings = {
            "line": VisualizationType.LINE,
            "lines": VisualizationType.LINE,
            "area": VisualizationType.AREA,
            "bars": VisualizationType.BAR,
            "bar": VisualizationType.BAR,
            "stacked_area": VisualizationType.STACKED_AREA,
            "stacked_bar": VisualizationType.STACKED_BAR,
            "scatter": VisualizationType.SCATTER,
            "points": VisualizationType.SCATTER,
        }
        
        return mappings.get(type_lower, VisualizationType.OTHER)

    @staticmethod
    def map_monitor_status(status: str, provider: str) -> MonitorStatus:
        """Map provider-specific monitor status to universal status."""
        status_lower = status.lower()
        
        # Common status mappings
        ok_statuses = {"ok", "good", "normal", "resolved", "inactive", "no_alert"}
        warning_statuses = {"warn", "warning", "pending"}
        alert_statuses = {"alert", "alerting", "critical", "error", "triggered", "firing"}
        no_data_statuses = {"no_data", "nodata", "no data", "unknown", "stale"}
        muted_statuses = {"muted", "silenced", "paused", "disabled"}
        
        if status_lower in ok_statuses:
            return MonitorStatus.OK
        elif status_lower in warning_statuses:
            return MonitorStatus.WARNING
        elif status_lower in alert_statuses:
            return MonitorStatus.ALERT
        elif status_lower in no_data_statuses:
            return MonitorStatus.NO_DATA
        elif status_lower in muted_statuses:
            return MonitorStatus.MUTED
        else:
            return MonitorStatus.UNKNOWN

    @staticmethod
    def map_monitor_type(type_str: str, provider: str) -> MonitorType:
        """Map provider-specific monitor type to universal type."""
        type_lower = type_str.lower()
        
        mappings = {
            "metric": MonitorType.METRIC,
            "metric alert": MonitorType.METRIC,
            "query alert": MonitorType.METRIC,
            "log": MonitorType.LOG,
            "log alert": MonitorType.LOG,
            "logs": MonitorType.LOG,
            "apm": MonitorType.APM,
            "trace": MonitorType.APM,
            "trace analytics": MonitorType.APM,
            "synthetics": MonitorType.SYNTHETICS,
            "synthetic": MonitorType.SYNTHETICS,
            "composite": MonitorType.COMPOSITE,
            "process": MonitorType.PROCESS,
            "live process": MonitorType.PROCESS,
            "network": MonitorType.NETWORK,
            "anomaly": MonitorType.ANOMALY,
            "anomaly detection": MonitorType.ANOMALY,
            "forecast": MonitorType.FORECAST,
            "outlier": MonitorType.OUTLIER,
        }
        
        return mappings.get(type_lower, MonitorType.OTHER)

    @staticmethod
    def map_severity(severity: str) -> AlertSeverity:
        """Map severity strings to AlertSeverity enum."""
        severity_lower = severity.lower()
        
        if severity_lower in {"critical", "p1", "sev1", "1"}:
            return AlertSeverity.CRITICAL
        elif severity_lower in {"high", "p2", "sev2", "2"}:
            return AlertSeverity.HIGH
        elif severity_lower in {"medium", "p3", "sev3", "3", "normal"}:
            return AlertSeverity.MEDIUM
        elif severity_lower in {"low", "p4", "sev4", "4"}:
            return AlertSeverity.LOW
        elif severity_lower in {"info", "p5", "sev5", "5", "informational"}:
            return AlertSeverity.INFO
        else:
            return AlertSeverity.MEDIUM
