"""Provider adapters for metrics exploration."""

from app.adapters.base import BaseAdapter, AdapterFactory
from app.models.organization import ProviderType

# Import adapters (this triggers their module-level registration if they have it)
from app.adapters import datadog, prometheus, grafana  # noqa: F401

# Register adapters explicitly
from app.adapters.datadog.adapter import DatadogAdapter
from app.adapters.prometheus.adapter import PrometheusAdapter
from app.adapters.grafana.adapter import GrafanaAdapter

# Register all adapters with the factory
AdapterFactory.register(ProviderType.DATADOG, DatadogAdapter)
AdapterFactory.register(ProviderType.PROMETHEUS, PrometheusAdapter)
AdapterFactory.register(ProviderType.GRAFANA, GrafanaAdapter)

__all__ = ["BaseAdapter", "AdapterFactory"]
