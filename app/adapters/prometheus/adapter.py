"""Prometheus adapter implementation for transforming Prometheus data to OTel format."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.adapters.base import (
    AdapterError,
    AdapterNotFoundError,
    AdapterQueryError,
    BaseAdapter,
    AdapterFactory,
)
from app.adapters.prometheus.client import PrometheusClient
from app.models.dashboard import Dashboard, DashboardList, DashboardSummary
from app.models.metrics import (
    Metric,
    MetricDataPoint,
    MetricMetadata,
    MetricMetadataList,
    MetricQuery,
    MetricQueryResult,
    MetricType,
    ResourceAttributes,
)
from app.models.monitor import (
    AlertSeverity,
    Monitor,
    MonitorList,
    MonitorQuery,
    MonitorStatus,
    MonitorSummary,
    MonitorThreshold,
    MonitorType,
)
from app.models.organization import OrganizationProvider, ProviderType
from app.utils.transformers import OTelTransformer

logger = structlog.get_logger(__name__)


class PrometheusAdapter(BaseAdapter):
    """Adapter for Prometheus metrics and alerting rules."""

    def __init__(
        self,
        provider_config: OrganizationProvider,
        credentials: Dict[str, Any],
    ):
        super().__init__(provider_config, credentials)
        
        # Use endpoint_url from config, fall back to credentials
        endpoint = self.endpoint_url or credentials.get("url", "http://localhost:9090")
        
        self.client = PrometheusClient(
            base_url=endpoint,
            username=credentials.get("username"),
            password=credentials.get("password"),
            bearer_token=credentials.get("bearer_token"),
            timeout=self.config.timeout_seconds,
        )

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.PROMETHEUS

    # ==================== Dashboard Methods ====================
    # Note: Prometheus doesn't have native dashboards - these return empty results
    # For dashboard functionality, use Grafana adapter

    async def list_dashboards(
        self,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DashboardList:
        """
        Prometheus doesn't have native dashboards.
        Returns empty list - use Grafana for dashboard functionality.
        """
        return DashboardList(
            dashboards=[],
            total_count=0,
            providers_queried=[self.provider_name],
        )

    async def get_dashboard(self, dashboard_id: str) -> Dashboard:
        """Prometheus doesn't have dashboards."""
        raise AdapterNotFoundError(
            "Prometheus does not support dashboards. Use Grafana adapter.",
            self.provider_name,
        )

    # ==================== Monitor Methods ====================
    # Prometheus alerting rules are treated as monitors

    async def list_monitors(
        self,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> MonitorList:
        """List Prometheus alerting rules as monitors."""
        try:
            self._log_request("list_monitors")
            
            # Get alerting rules
            rules_response = await self.client.list_rules(type="alert")
            
            monitors = []
            status_counts: Dict[str, int] = {}
            
            for group in rules_response.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("type") == "alerting":
                        monitor = self._rule_to_monitor_summary(rule, group.get("name"))
                        
                        # Filter by status if provided
                        if status and monitor.status.value != status.lower():
                            continue
                        
                        # Filter by tags if provided (match against labels)
                        if tags:
                            rule_labels = rule.get("labels", {})
                            if not any(
                                t in rule_labels.keys() or t in rule_labels.values()
                                for t in tags
                            ):
                                continue
                        
                        monitors.append(monitor)
                        status_counts[monitor.status.value] = (
                            status_counts.get(monitor.status.value, 0) + 1
                        )
            
            # Apply pagination
            total = len(monitors)
            monitors = monitors[offset:offset + limit]
            
            return MonitorList(
                monitors=monitors,
                total_count=total,
                providers_queried=[self.provider_name],
                status_counts=status_counts,
            )
        except Exception as e:
            self._handle_error("list_monitors", e)
            raise AdapterQueryError(str(e), self.provider_name)

    async def get_monitor(self, monitor_id: str) -> Monitor:
        """Get detailed Prometheus alerting rule."""
        try:
            self._log_request("get_monitor", monitor_id=monitor_id)
            
            # Get all rules and find the matching one
            rules_response = await self.client.list_rules(type="alert")
            
            for group in rules_response.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("name") == monitor_id:
                        return self._rule_to_monitor(rule, group.get("name"))
            
            raise AdapterNotFoundError(
                f"Alert rule not found: {monitor_id}",
                self.provider_name,
            )
        except AdapterNotFoundError:
            raise
        except Exception as e:
            self._handle_error("get_monitor", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _rule_to_monitor_summary(
        self, rule: Dict[str, Any], group_name: str
    ) -> MonitorSummary:
        """Convert Prometheus alerting rule to monitor summary."""
        # Determine status from rule state
        state = rule.get("state", "inactive")
        status = self._map_prometheus_state(state)
        
        # Get severity from labels
        labels = rule.get("labels", {})
        severity = labels.get("severity", "warning")
        
        return MonitorSummary(
            id=rule.get("name", ""),
            name=rule.get("name", "Untitled"),
            description=rule.get("annotations", {}).get("description"),
            monitor_type=MonitorType.METRIC,
            status=status,
            priority=OTelTransformer.map_severity(severity),
            tags=list(labels.keys()),
            is_muted=False,
            last_triggered_at=self._parse_timestamp(
                rule.get("lastEvaluation")
            ) if state == "firing" else None,
            url=None,
            provider_source=self.provider_name,
        )

    def _rule_to_monitor(
        self, rule: Dict[str, Any], group_name: str
    ) -> Monitor:
        """Convert Prometheus alerting rule to full monitor."""
        state = rule.get("state", "inactive")
        labels = rule.get("labels", {})
        annotations = rule.get("annotations", {})
        
        # Build query from PromQL expression
        expr = rule.get("query", rule.get("expr", ""))
        queries = [
            MonitorQuery(
                query_id="main",
                raw_query=expr,
                metric_names=self._extract_metric_names(expr),
                evaluation_window_seconds=self._parse_duration(rule.get("for", "0s")),
            )
        ] if expr else []
        
        return Monitor(
            id=rule.get("name", ""),
            name=rule.get("name", "Untitled"),
            description=annotations.get("description") or annotations.get("summary"),
            resource=self._build_resource_from_labels(labels),
            monitor_type=MonitorType.METRIC,
            queries=queries,
            thresholds=[],  # Thresholds are embedded in PromQL expression
            status=self._map_prometheus_state(state),
            current_value=None,
            last_evaluated_at=self._parse_timestamp(rule.get("lastEvaluation")),
            last_triggered_at=self._parse_timestamp(
                rule.get("lastEvaluation")
            ) if state == "firing" else None,
            recent_state_changes=[],
            notifications=[],
            tags=list(labels.keys()),
            priority=OTelTransformer.map_severity(labels.get("severity", "warning")),
            is_muted=False,
            mute_until=None,
            created_by=None,
            modified_by=None,
            created_at=None,
            modified_at=None,
            url=None,
            provider_source=self.provider_name,
            provider_monitor_type="alerting_rule",
            provider_metadata={
                "group": group_name,
                "for": rule.get("for"),
                "labels": labels,
                "annotations": annotations,
                "health": rule.get("health"),
                "alerts": rule.get("alerts", []),
            },
        )

    def _map_prometheus_state(self, state: str) -> MonitorStatus:
        """Map Prometheus alert state to MonitorStatus."""
        state_lower = state.lower()
        if state_lower == "firing":
            return MonitorStatus.ALERT
        elif state_lower == "pending":
            return MonitorStatus.WARNING
        elif state_lower == "inactive":
            return MonitorStatus.OK
        else:
            return MonitorStatus.UNKNOWN

    # ==================== Metrics Methods ====================

    async def query_metrics(self, query: MetricQuery) -> MetricQueryResult:
        """Query Prometheus metrics."""
        try:
            self._log_request("query_metrics")
            
            start_ts = query.start_time.timestamp()
            end_ts = query.end_time.timestamp()
            
            # Build PromQL query
            promql = self._build_promql_query(query)
            
            # Calculate step
            step = f"{query.step_seconds}s" if query.step_seconds else "60s"
            
            start_time = datetime.now(timezone.utc)
            response = await self.client.range_query(promql, start_ts, end_ts, step)
            query_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            metrics = self._parse_metrics_response(response)
            
            return MetricQueryResult(
                metrics=metrics,
                query=query,
                total_count=len(metrics),
                query_time_ms=query_time,
                providers_queried=[self.provider_name],
            )
        except Exception as e:
            self._handle_error("query_metrics", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _build_promql_query(self, query: MetricQuery) -> str:
        """Build PromQL query from universal query."""
        if query.metric_names:
            metric = query.metric_names[0]
            
            # Build label matchers
            matchers = []
            for key, value in query.attribute_filters.items():
                matchers.append(f'{key}="{value}"')
            
            for key, value in query.resource_filters.items():
                matchers.append(f'{key}="{value}"')
            
            matcher_str = "{" + ",".join(matchers) + "}" if matchers else ""
            base_query = f"{metric}{matcher_str}"
            
            # Apply aggregation
            if query.aggregation:
                agg = query.aggregation.lower()
                if query.group_by:
                    by_clause = " by (" + ",".join(query.group_by) + ")"
                else:
                    by_clause = ""
                return f"{agg}({base_query}){by_clause}"
            
            return base_query
        
        return query.metric_name_pattern or "up"

    def _parse_metrics_response(self, response: Dict[str, Any]) -> List[Metric]:
        """Parse Prometheus query response to universal format."""
        metrics = []
        
        data = response.get("data", {})
        result_type = data.get("resultType", "matrix")
        results = data.get("result", [])
        
        for series in results:
            metric_labels = series.get("metric", {})
            metric_name = metric_labels.pop("__name__", "unknown")
            
            data_points = []
            
            if result_type == "matrix":
                # Range query - array of [timestamp, value] pairs
                for point in series.get("values", []):
                    timestamp, value = point
                    data_points.append(MetricDataPoint(
                        time=datetime.fromtimestamp(float(timestamp), tz=timezone.utc),
                        value=float(value) if value != "NaN" else 0,
                        attributes=metric_labels,
                    ))
            else:
                # Instant query - single [timestamp, value]
                point = series.get("value", [])
                if len(point) >= 2:
                    timestamp, value = point
                    data_points.append(MetricDataPoint(
                        time=datetime.fromtimestamp(float(timestamp), tz=timezone.utc),
                        value=float(value) if value != "NaN" else 0,
                        attributes=metric_labels,
                    ))
            
            metrics.append(Metric(
                name=OTelTransformer.normalize_metric_name(metric_name, "prometheus"),
                description=None,
                unit=None,
                metric_type=self._infer_metric_type(metric_name),
                data_points=data_points,
                resource=self._build_resource_from_labels(metric_labels),
                provider_source=self.provider_name,
                provider_metadata={
                    "original_name": metric_name,
                    "labels": metric_labels,
                },
            ))
        
        return metrics

    def _infer_metric_type(self, metric_name: str) -> MetricType:
        """Infer metric type from name conventions."""
        name_lower = metric_name.lower()
        
        if name_lower.endswith("_total") or name_lower.endswith("_count"):
            return MetricType.SUM
        elif name_lower.endswith("_bucket"):
            return MetricType.HISTOGRAM
        elif name_lower.endswith("_sum"):
            return MetricType.SUM
        else:
            return MetricType.GAUGE

    async def get_metric_metadata(
        self,
        metric_names: Optional[List[str]] = None,
        limit: int = 100,
    ) -> MetricMetadataList:
        """Get Prometheus metric metadata."""
        try:
            self._log_request("get_metric_metadata")
            
            # Get metadata from Prometheus
            response = await self.client.get_metadata(limit=limit)
            
            metadata_dict = response.get("data", {})
            
            # Filter if specific names requested
            if metric_names:
                metadata_dict = {
                    k: v for k, v in metadata_dict.items()
                    if k in metric_names
                }
            
            # Convert to MetricMetadata
            metadata = []
            for name, info_list in metadata_dict.items():
                if info_list:
                    info = info_list[0]  # Take first entry
                    metadata.append(MetricMetadata(
                        name=OTelTransformer.normalize_metric_name(name, "prometheus"),
                        description=info.get("help"),
                        unit=info.get("unit"),
                        metric_type=self._map_prometheus_type(info.get("type", "gauge")),
                        available_attributes=[],
                        provider_source=self.provider_name,
                        help_text=info.get("help"),
                    ))
            
            return MetricMetadataList(
                metrics=metadata[:limit],
                total_count=len(metadata),
                providers_queried=[self.provider_name],
            )
        except Exception as e:
            self._handle_error("get_metric_metadata", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _map_prometheus_type(self, prom_type: str) -> MetricType:
        """Map Prometheus metric type to universal type."""
        type_map = {
            "counter": MetricType.SUM,
            "gauge": MetricType.GAUGE,
            "histogram": MetricType.HISTOGRAM,
            "summary": MetricType.SUMMARY,
        }
        return type_map.get(prom_type.lower(), MetricType.GAUGE)

    # ==================== Helper Methods ====================

    def _build_resource_from_labels(self, labels: Dict[str, str]) -> ResourceAttributes:
        """Build resource attributes from Prometheus labels."""
        return ResourceAttributes(
            service_name=labels.get("job") or labels.get("service"),
            service_instance_id=labels.get("instance"),
            deployment_environment=labels.get("env") or labels.get("environment"),
            k8s_namespace_name=labels.get("namespace"),
            k8s_pod_name=labels.get("pod"),
            custom={k: v for k, v in labels.items()},
        )

    def _extract_metric_names(self, expr: str) -> List[str]:
        """Extract metric names from PromQL expression."""
        import re
        # Match metric names (alphanumeric + underscore, not starting with number)
        pattern = r'\b([a-zA-Z_:][a-zA-Z0-9_:]*)\s*[{\(]?'
        matches = re.findall(pattern, expr)
        # Filter out PromQL functions
        functions = {
            "sum", "avg", "min", "max", "count", "rate", "irate",
            "increase", "histogram_quantile", "absent", "abs", "ceil",
            "floor", "exp", "ln", "log2", "log10", "sqrt", "round",
            "label_join", "label_replace", "vector", "scalar", "time",
            "by", "without", "on", "ignoring", "group_left", "group_right",
        }
        return list(set(m for m in matches if m.lower() not in functions))

    def _parse_duration(self, duration: str) -> int:
        """Parse Prometheus duration string to seconds."""
        if not duration:
            return 0
        
        import re
        match = re.match(r'^(\d+)(ms|s|m|h|d|w|y)$', duration)
        if not match:
            return 0
        
        value = int(match.group(1))
        unit = match.group(2)
        
        multipliers = {
            "ms": 0.001,
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800,
            "y": 31536000,
        }
        
        return int(value * multipliers.get(unit, 1))

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not value:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        
        return None

    async def health_check(self) -> bool:
        """Check Prometheus health."""
        return await self.client.health()


# Register adapter with factory
AdapterFactory.register(ProviderType.PROMETHEUS, PrometheusAdapter)
