"""Base adapter interface for metrics providers."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

import structlog

from app.models.dashboard import Dashboard, DashboardList, DashboardSummary
from app.models.query import (
    DashboardQueryRequest,
    DashboardQueryResponse,
    MetricQueryItem,
    QueryResultItem,
)
from app.models.metrics import (
    Metric,
    MetricMetadata,
    MetricMetadataList,
    MetricQuery,
    MetricQueryResult,
)
from app.models.monitor import Monitor, MonitorList, MonitorSummary
from app.models.organization import OrganizationProvider, ProviderConfig, ProviderType

logger = structlog.get_logger(__name__)


class AdapterError(Exception):
    """Base exception for adapter errors."""

    def __init__(self, message: str, provider: str, details: Optional[Dict] = None):
        self.provider = provider
        self.details = details or {}
        super().__init__(f"[{provider}] {message}")


class AdapterConnectionError(AdapterError):
    """Raised when connection to provider fails."""
    pass


class AdapterAuthenticationError(AdapterError):
    """Raised when authentication fails."""
    pass


class AdapterQueryError(AdapterError):
    """Raised when a query fails."""
    pass


class AdapterNotFoundError(AdapterError):
    """Raised when a resource is not found."""
    pass


class BaseAdapter(ABC):
    """
    Abstract base class for metrics provider adapters.
    
    All provider adapters must implement this interface to ensure
    consistent behavior and data transformation to OTel format.
    """

    def __init__(
        self,
        provider_config: OrganizationProvider,
        credentials: Dict[str, Any],
    ):
        """
        Initialize the adapter with provider configuration.
        
        Args:
            provider_config: Provider configuration from database
            credentials: Decrypted provider credentials
        """
        self.provider_config = provider_config
        self.credentials = credentials
        self.provider_name = provider_config.provider_type.value
        self.config: ProviderConfig = provider_config.config
        self.endpoint_url = provider_config.endpoint_url
        
        self._logger = logger.bind(
            provider=self.provider_name,
            provider_id=str(provider_config.id),
        )

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type this adapter handles."""
        pass

    # ==================== Dashboard Methods ====================

    @abstractmethod
    async def list_dashboards(
        self,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DashboardList:
        """
        List all dashboards from the provider.
        
        Args:
            tags: Optional filter by tags
            folder: Optional filter by folder
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            DashboardList with dashboard summaries
        """
        pass

    @abstractmethod
    async def get_dashboard(self, dashboard_id: str) -> Dashboard:
        """
        Get detailed dashboard by ID.
        
        Args:
            dashboard_id: Dashboard identifier
            
        Returns:
            Full Dashboard object with widgets
            
        Raises:
            AdapterNotFoundError: If dashboard not found
        """
        pass

    # ==================== Monitor Methods ====================

    @abstractmethod
    async def list_monitors(
        self,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> MonitorList:
        """
        List all monitors from the provider.
        
        Args:
            tags: Optional filter by tags
            status: Optional filter by status
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            MonitorList with monitor summaries
        """
        pass

    @abstractmethod
    async def get_monitor(self, monitor_id: str) -> Monitor:
        """
        Get detailed monitor by ID.
        
        Args:
            monitor_id: Monitor identifier
            
        Returns:
            Full Monitor object
            
        Raises:
            AdapterNotFoundError: If monitor not found
        """
        pass

    # ==================== Metrics Methods ====================

    @abstractmethod
    async def query_metrics(self, query: MetricQuery) -> MetricQueryResult:
        """
        Query metrics from the provider.
        
        Args:
            query: MetricQuery with filters and time range
            
        Returns:
            MetricQueryResult with metrics data
        """
        pass

    @abstractmethod
    async def get_metric_metadata(
        self,
        metric_names: Optional[List[str]] = None,
        limit: int = 100,
    ) -> MetricMetadataList:
        """
        Get metadata for available metrics.
        
        Args:
            metric_names: Optional specific metrics to get metadata for
            limit: Maximum number of results
            
        Returns:
            MetricMetadataList with metric metadata
        """
        pass

    # ==================== Template Variable Resolution ====================

    async def resolve_template_variables(
        self,
        template_variables: List[Dict[str, Any]],
        dashboard_metrics: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Resolve template variable definitions to their possible values.
        
        Each provider implements this differently:
        - Datadog: calls GET /api/v1/tags/hosts, matches variable prefix to tag key,
                   then falls back to querying dashboard metrics for unresolved tags
        - Grafana: calls /api/datasources, etc.
        - Prometheus: label values queries
        
        Default implementation returns the variable definitions as-is (no resolution).
        
        Args:
            template_variables: List of provider-specific variable definitions.
                For Datadog: [{"name": "env", "prefix": "env", "default": "*", "available_values": []}, ...]
            dashboard_metrics: Optional list of metric names used in the dashboard's
                widgets.  Used as a fallback source for resolving metric-level tags
                that don't appear in host tags.
                
        Returns:
            Dict keyed by variable name, each containing:
                {
                    "name": "env",
                    "tag_key": "env",           # the tag/label key this maps to
                    "default": "*",
                    "values": ["prod", "staging", ...],  # resolved possible values
                }
        """
        # Default: pass-through with no resolution
        result: Dict[str, Dict[str, Any]] = {}
        for var in template_variables:
            name = var.get("name", "")
            if name:
                result[name] = {
                    "name": name,
                    "tag_key": var.get("prefix") or var.get("tag_key") or name,
                    "default": var.get("default", "*"),
                    "values": var.get("available_values") or [],
                }
        return result

    # ==================== Dashboard Query Execution ====================

    async def execute_queries(
        self,
        request: DashboardQueryRequest,
        dashboard_id: str,
    ) -> DashboardQueryResponse:
        """
        Execute a batch of metric queries for a dashboard.

        Each provider translates the universal ``MetricQueryItem`` entries
        into its native query language, executes them, and returns results
        in a unified ``DashboardQueryResponse``.

        The default implementation calls :meth:`query_metrics` once per
        item.  Providers that support batch querying should override this
        for better performance.

        Args:
            request: The batch query request with metric queries and time range.
            dashboard_id: The provider dashboard ID (for logging/context).

        Returns:
            Unified ``DashboardQueryResponse``.
        """
        from datetime import datetime as dt, timezone as tz

        overall_start = dt.now(tz.utc)
        start_ts, end_ts = request.time_range.resolve()

        results: List[QueryResultItem] = []
        total_series = 0
        total_dp = 0

        for idx, q_item in enumerate(request.queries):
            try:
                mq = MetricQuery(
                    metric_names=[q_item.metric_name],
                    start_time=dt.fromtimestamp(start_ts, tz=tz.utc),
                    end_time=dt.fromtimestamp(end_ts, tz=tz.utc),
                    attribute_filters={
                        k: v if isinstance(v, str) else ",".join(v)
                        for k, v in q_item.filters.items()
                    },
                    aggregation=q_item.aggregation,
                    group_by=q_item.group_by,
                )
                result = await self.query_metrics(mq)

                series_list = []
                dp_count = 0
                for m in result.metrics:
                    from app.models.query import Series, DataPoint

                    dps = [
                        DataPoint(
                            timestamp=int(dp.time.timestamp() * 1000),
                            value=dp.value if isinstance(dp.value, (int, float)) else None,
                        )
                        for dp in m.data_points
                    ]
                    dp_count += len(dps)
                    series_list.append(
                        Series(
                            scope=m.provider_metadata.get("expression", ""),
                            tags=m.data_points[0].attributes if m.data_points else {},
                            datapoints=dps,
                            unit=m.unit,
                        )
                    )

                total_series += len(series_list)
                total_dp += dp_count

                results.append(
                    QueryResultItem(
                        query_index=idx,
                        metric_name=q_item.metric_name,
                        expression=None,
                        series=series_list,
                        series_count=len(series_list),
                        datapoint_count=dp_count,
                        query_time_ms=result.query_time_ms,
                    )
                )
            except Exception as e:
                self._logger.error(
                    "Query execution failed for item",
                    query_index=idx,
                    metric=q_item.metric_name,
                    error=str(e),
                )
                results.append(
                    QueryResultItem(
                        query_index=idx,
                        metric_name=q_item.metric_name,
                        series=[],
                        error=str(e),
                    )
                )

        elapsed = int(
            (dt.now(tz.utc) - overall_start).total_seconds() * 1000
        )

        return DashboardQueryResponse(
            dashboard_id=dashboard_id,
            provider=self.provider_name,
            results=results,
            total_queries=len(request.queries),
            total_series=total_series,
            total_datapoints=total_dp,
            execution_time_ms=elapsed,
        )

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """
        Check if the provider connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Default implementation - try to list dashboards with limit 1
            await self.list_dashboards(limit=1)
            return True
        except Exception as e:
            self._logger.warning("Health check failed", error=str(e))
            return False

    # ==================== Helper Methods ====================

    def _log_request(self, operation: str, **kwargs):
        """Log an API request."""
        self._logger.debug(f"API request: {operation}", **kwargs)

    def _log_response(self, operation: str, status: str, **kwargs):
        """Log an API response."""
        self._logger.debug(f"API response: {operation}", status=status, **kwargs)

    def _handle_error(self, operation: str, error: Exception) -> None:
        """Log and handle errors consistently."""
        self._logger.error(
            f"API error: {operation}",
            error=str(error),
            error_type=type(error).__name__,
        )


class AdapterFactory:
    """Factory for creating provider adapters."""

    _adapters: Dict[ProviderType, Type[BaseAdapter]] = {}

    @classmethod
    def register(cls, provider_type: ProviderType, adapter_class: Type[BaseAdapter]):
        """Register an adapter class for a provider type."""
        cls._adapters[provider_type] = adapter_class
        logger.info(
            "Registered adapter",
            provider_type=provider_type.value,
            adapter_class=adapter_class.__name__,
        )

    @classmethod
    def create(
        cls,
        provider_config: OrganizationProvider,
        credentials: Dict[str, Any],
    ) -> BaseAdapter:
        """
        Create an adapter instance for the given provider configuration.
        
        Args:
            provider_config: Provider configuration
            credentials: Decrypted credentials
            
        Returns:
            Configured adapter instance
            
        Raises:
            ValueError: If no adapter registered for provider type
        """
        adapter_class = cls._adapters.get(provider_config.provider_type)
        if not adapter_class:
            raise ValueError(
                f"No adapter registered for provider type: "
                f"{provider_config.provider_type.value}"
            )
        
        return adapter_class(provider_config, credentials)

    @classmethod
    def get_supported_providers(cls) -> List[ProviderType]:
        """Get list of supported provider types."""
        return list(cls._adapters.keys())
