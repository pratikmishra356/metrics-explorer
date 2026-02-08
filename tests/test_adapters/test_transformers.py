"""Tests for OTel transformers."""

import pytest
from datetime import datetime, timezone

from app.utils.transformers import OTelTransformer
from app.models.metrics import MetricType, ResourceAttributes
from app.models.dashboard import WidgetType
from app.models.monitor import MonitorStatus, MonitorType, AlertSeverity


class TestOTelTransformer:
    """Tests for OTelTransformer utility class."""

    def test_normalize_metric_name(self):
        """Test metric name normalization."""
        # Test underscore to dot conversion
        assert OTelTransformer.normalize_metric_name(
            "cpu_usage_percent", "datadog"
        ) == "cpu.usage.percent"
        
        # Test provider prefix removal
        assert OTelTransformer.normalize_metric_name(
            "datadog.cpu_usage", "datadog"
        ) == "cpu.usage"
        
        # Test double dot removal
        assert OTelTransformer.normalize_metric_name(
            "system..cpu", "prometheus"
        ) == "system.cpu"

    def test_normalize_attribute_key(self):
        """Test attribute key normalization."""
        # Test known mappings
        assert OTelTransformer.normalize_attribute_key("service") == "service.name"
        assert OTelTransformer.normalize_attribute_key("env") == "deployment.environment"
        assert OTelTransformer.normalize_attribute_key("host") == "host.name"
        
        # Test unknown keys
        assert OTelTransformer.normalize_attribute_key("custom_key") == "custom.key"

    def test_map_widget_type(self):
        """Test widget type mapping."""
        assert OTelTransformer.map_widget_type("timeseries", "grafana") == WidgetType.TIMESERIES
        assert OTelTransformer.map_widget_type("graph", "datadog") == WidgetType.TIMESERIES
        assert OTelTransformer.map_widget_type("table", "grafana") == WidgetType.TABLE
        assert OTelTransformer.map_widget_type("unknown_type", "any") == WidgetType.OTHER

    def test_map_monitor_status(self):
        """Test monitor status mapping."""
        assert OTelTransformer.map_monitor_status("ok", "datadog") == MonitorStatus.OK
        assert OTelTransformer.map_monitor_status("alerting", "grafana") == MonitorStatus.ALERT
        assert OTelTransformer.map_monitor_status("firing", "prometheus") == MonitorStatus.ALERT
        assert OTelTransformer.map_monitor_status("warn", "any") == MonitorStatus.WARNING
        assert OTelTransformer.map_monitor_status("no_data", "any") == MonitorStatus.NO_DATA
        assert OTelTransformer.map_monitor_status("muted", "any") == MonitorStatus.MUTED

    def test_map_monitor_type(self):
        """Test monitor type mapping."""
        assert OTelTransformer.map_monitor_type("metric alert", "datadog") == MonitorType.METRIC
        assert OTelTransformer.map_monitor_type("log alert", "datadog") == MonitorType.LOG
        assert OTelTransformer.map_monitor_type("apm", "any") == MonitorType.APM
        assert OTelTransformer.map_monitor_type("unknown", "any") == MonitorType.OTHER

    def test_map_severity(self):
        """Test severity mapping."""
        assert OTelTransformer.map_severity("critical") == AlertSeverity.CRITICAL
        assert OTelTransformer.map_severity("high") == AlertSeverity.HIGH
        assert OTelTransformer.map_severity("p1") == AlertSeverity.CRITICAL
        assert OTelTransformer.map_severity("info") == AlertSeverity.INFO
        assert OTelTransformer.map_severity("unknown") == AlertSeverity.MEDIUM

    def test_create_resource_attributes(self):
        """Test resource attributes creation."""
        attrs = OTelTransformer.create_resource_attributes(
            service_name="my-service",
            deployment_environment="production",
            host_name="host-1",
            custom={"custom_key": "value"},
        )
        
        assert attrs.service_name == "my-service"
        assert attrs.deployment_environment == "production"
        assert attrs.host_name == "host-1"
        assert attrs.custom == {"custom_key": "value"}

    def test_create_metric(self):
        """Test metric creation."""
        metric = OTelTransformer.create_metric(
            name="system.cpu.utilization",
            metric_type=MetricType.GAUGE,
            provider_source="prometheus",
            description="CPU utilization percentage",
            unit="percent",
        )
        
        assert metric.name == "system.cpu.utilization"
        assert metric.metric_type == MetricType.GAUGE
        assert metric.provider_source == "prometheus"
        assert metric.description == "CPU utilization percentage"
        assert metric.unit == "percent"

    def test_create_data_point(self):
        """Test data point creation."""
        now = datetime.now(timezone.utc)
        point = OTelTransformer.create_data_point(
            time=now,
            value=42.5,
            attributes={"host": "server-1"},
        )
        
        assert point.time == now
        assert point.value == 42.5
        assert point.attributes == {"host": "server-1"}
