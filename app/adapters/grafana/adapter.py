"""Grafana adapter implementation for transforming Grafana data to OTel format."""

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
from app.adapters.grafana.client import GrafanaClient
from app.models.dashboard import (
    Dashboard,
    DashboardList,
    DashboardSummary,
    DashboardWidget,
    DashboardWidgetQuery,
    VisualizationType,
    WidgetType,
)
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


class GrafanaAdapter(BaseAdapter):
    """Adapter for Grafana dashboards, alerts, and datasource queries."""

    def __init__(
        self,
        provider_config: OrganizationProvider,
        credentials: Dict[str, Any],
    ):
        super().__init__(provider_config, credentials)
        
        # Use endpoint_url from config, fall back to credentials
        endpoint = self.endpoint_url or credentials.get("url", "http://localhost:3000")
        
        self.client = GrafanaClient(
            base_url=endpoint,
            api_key=credentials.get("api_key", ""),
            timeout=self.config.timeout_seconds,
        )

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GRAFANA

    # ==================== Dashboard Methods ====================

    async def list_dashboards(
        self,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DashboardList:
        """List Grafana dashboards."""
        try:
            self._log_request("list_dashboards")
            
            # Search dashboards
            dashboards = await self.client.search_dashboards(
                tag=tags,
                type_="dash-db",
                limit=1000,  # Get all, then paginate
            )
            
            # Filter by folder if provided
            if folder:
                dashboards = [
                    d for d in dashboards
                    if d.get("folderTitle", "").lower() == folder.lower()
                    or d.get("folderUid") == folder
                ]
            
            # Apply pagination
            total = len(dashboards)
            dashboards = dashboards[offset:offset + limit]
            
            summaries = [self._to_dashboard_summary(d) for d in dashboards]
            
            return DashboardList(
                dashboards=summaries,
                total_count=total,
                providers_queried=[self.provider_name],
            )
        except Exception as e:
            self._handle_error("list_dashboards", e)
            raise AdapterQueryError(str(e), self.provider_name)

    async def get_dashboard(self, dashboard_id: str) -> Dashboard:
        """Get detailed Grafana dashboard."""
        try:
            self._log_request("get_dashboard", dashboard_id=dashboard_id)
            
            # Try to get by UID first, then by ID
            try:
                response = await self.client.get_dashboard_by_uid(dashboard_id)
            except Exception:
                # Try as numeric ID
                try:
                    response = await self.client.get_dashboard_by_id(int(dashboard_id))
                except (ValueError, Exception):
                    raise AdapterNotFoundError(
                        f"Dashboard not found: {dashboard_id}",
                        self.provider_name,
                    )
            
            return self._to_dashboard(response)
        except AdapterNotFoundError:
            raise
        except Exception as e:
            self._handle_error("get_dashboard", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _to_dashboard_summary(self, data: Dict[str, Any]) -> DashboardSummary:
        """Convert Grafana search result to dashboard summary."""
        return DashboardSummary(
            id=data.get("uid", str(data.get("id", ""))),
            title=data.get("title", "Untitled"),
            description=None,  # Not available in search results
            tags=data.get("tags", []),
            folder=data.get("folderTitle"),
            widget_count=0,  # Not available in search
            created_at=None,
            modified_at=None,
            url=data.get("url"),
            provider_source=self.provider_name,
        )

    def _to_dashboard(self, response: Dict[str, Any]) -> Dashboard:
        """Convert Grafana dashboard response to universal format."""
        dashboard = response.get("dashboard", {})
        meta = response.get("meta", {})
        
        # Extract panels/widgets
        panels = dashboard.get("panels", [])
        widgets = []
        for idx, panel in enumerate(panels):
            widget = self._to_widget(panel, idx)
            if widget:
                widgets.append(widget)
        
        return Dashboard(
            id=dashboard.get("uid", str(dashboard.get("id", ""))),
            title=dashboard.get("title", "Untitled"),
            description=dashboard.get("description"),
            resource=ResourceAttributes(),
            widgets=widgets,
            tags=dashboard.get("tags", []),
            folder=meta.get("folderTitle"),
            default_time_range={
                "from": dashboard.get("time", {}).get("from"),
                "to": dashboard.get("time", {}).get("to"),
            } if dashboard.get("time") else None,
            refresh_interval=dashboard.get("refresh"),
            created_by=meta.get("createdBy"),
            modified_by=meta.get("updatedBy"),
            created_at=self._parse_timestamp(meta.get("created")),
            modified_at=self._parse_timestamp(meta.get("updated")),
            url=meta.get("url"),
            provider_source=self.provider_name,
            provider_dashboard_type=dashboard.get("schemaVersion"),
            provider_metadata={
                "uid": dashboard.get("uid"),
                "version": dashboard.get("version"),
                "editable": dashboard.get("editable"),
                "folder_id": meta.get("folderId"),
                "folder_uid": meta.get("folderUid"),
            },
        )

    def _to_widget(self, panel: Dict[str, Any], index: int) -> Optional[DashboardWidget]:
        """Convert Grafana panel to universal widget."""
        panel_type = panel.get("type", "")
        
        # Skip row panels
        if panel_type == "row":
            return None
        
        # Extract queries/targets
        queries = self._extract_panel_queries(panel)
        
        # Get grid position
        grid_pos = panel.get("gridPos", {})
        
        return DashboardWidget(
            id=str(panel.get("id", index)),
            title=panel.get("title", ""),
            description=panel.get("description"),
            widget_type=OTelTransformer.map_widget_type(panel_type, "grafana"),
            visualization_type=self._get_visualization_type(panel),
            position={
                "x": grid_pos.get("x", 0),
                "y": grid_pos.get("y", 0),
                "width": grid_pos.get("w", 12),
                "height": grid_pos.get("h", 8),
            },
            queries=queries,
            time_range=None,  # Panels inherit dashboard time range
            thresholds=self._extract_thresholds(panel),
            provider_widget_type=panel_type,
            provider_metadata={
                "datasource": panel.get("datasource"),
                "options": panel.get("options"),
                "fieldConfig": panel.get("fieldConfig"),
            },
        )

    def _extract_panel_queries(
        self, panel: Dict[str, Any]
    ) -> List[DashboardWidgetQuery]:
        """Extract queries from Grafana panel."""
        queries = []
        targets = panel.get("targets", [])
        
        for idx, target in enumerate(targets):
            # Different datasources have different query formats
            raw_query = (
                target.get("expr")  # Prometheus
                or target.get("query")  # Generic
                or target.get("rawSql")  # SQL
                or target.get("rawQuery")  # InfluxDB
                or str(target)
            )
            
            if raw_query:
                queries.append(DashboardWidgetQuery(
                    query_id=target.get("refId", f"q{idx}"),
                    raw_query=raw_query if isinstance(raw_query, str) else str(raw_query),
                    metric_names=[],  # Would need datasource-specific parsing
                    display_name=target.get("legendFormat"),
                ))
        
        return queries

    def _get_visualization_type(self, panel: Dict[str, Any]) -> Optional[VisualizationType]:
        """Get visualization type from panel configuration."""
        panel_type = panel.get("type", "")
        options = panel.get("options", {})
        field_config = panel.get("fieldConfig", {})
        
        # Map common Grafana panel types
        if panel_type in ("timeseries", "graph"):
            # Check for specific display modes
            display_mode = (
                options.get("legend", {}).get("displayMode")
                or field_config.get("defaults", {}).get("custom", {}).get("drawStyle")
            )
            if display_mode == "bars":
                return VisualizationType.BAR
            elif display_mode == "points":
                return VisualizationType.SCATTER
            return VisualizationType.LINE
        elif panel_type == "barchart":
            return VisualizationType.BAR
        elif panel_type == "bargauge":
            return VisualizationType.BAR
        elif panel_type == "gauge":
            return VisualizationType.SOLID_GAUGE
        
        return None

    def _extract_thresholds(self, panel: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract thresholds from panel configuration."""
        thresholds = []
        field_config = panel.get("fieldConfig", {})
        defaults = field_config.get("defaults", {})
        threshold_config = defaults.get("thresholds", {})
        
        for step in threshold_config.get("steps", []):
            if step.get("value") is not None:
                thresholds.append({
                    "value": step.get("value"),
                    "color": step.get("color"),
                })
        
        return thresholds

    # ==================== Monitor Methods ====================

    async def list_monitors(
        self,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> MonitorList:
        """List Grafana alert rules as monitors."""
        try:
            self._log_request("list_monitors")
            
            # Try unified alerting first (Grafana 8+)
            try:
                rules = await self.client.list_alert_rules()
                monitors = [
                    self._rule_to_monitor_summary(r)
                    for r in rules
                ]
            except Exception:
                # Fall back to legacy alerts
                alerts = await self.client.list_legacy_alerts()
                monitors = [
                    self._legacy_alert_to_monitor_summary(a)
                    for a in alerts
                ]
            
            # Filter by status if provided
            if status:
                monitors = [
                    m for m in monitors
                    if m.status.value == status.lower()
                ]
            
            # Calculate status counts
            status_counts: Dict[str, int] = {}
            for m in monitors:
                status_counts[m.status.value] = status_counts.get(m.status.value, 0) + 1
            
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
        """Get detailed Grafana alert rule."""
        try:
            self._log_request("get_monitor", monitor_id=monitor_id)
            
            try:
                rule = await self.client.get_alert_rule(monitor_id)
                return self._rule_to_monitor(rule)
            except Exception:
                raise AdapterNotFoundError(
                    f"Alert rule not found: {monitor_id}",
                    self.provider_name,
                )
        except AdapterNotFoundError:
            raise
        except Exception as e:
            self._handle_error("get_monitor", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _rule_to_monitor_summary(self, rule: Dict[str, Any]) -> MonitorSummary:
        """Convert Grafana alert rule to monitor summary."""
        # Determine status from rule state
        state = rule.get("state", "normal")
        labels = rule.get("labels", {})
        
        return MonitorSummary(
            id=rule.get("uid", ""),
            name=rule.get("title", "Untitled"),
            description=rule.get("annotations", {}).get("description"),
            monitor_type=MonitorType.METRIC,
            status=self._map_grafana_state(state),
            priority=OTelTransformer.map_severity(labels.get("severity", "warning")),
            tags=list(labels.keys()),
            is_muted=rule.get("isPaused", False),
            last_triggered_at=None,
            url=None,
            provider_source=self.provider_name,
        )

    def _legacy_alert_to_monitor_summary(self, alert: Dict[str, Any]) -> MonitorSummary:
        """Convert legacy Grafana alert to monitor summary."""
        state = alert.get("state", "unknown")
        
        return MonitorSummary(
            id=str(alert.get("id", "")),
            name=alert.get("name", "Untitled"),
            description=alert.get("message"),
            monitor_type=MonitorType.METRIC,
            status=self._map_grafana_state(state),
            priority=None,
            tags=[],
            is_muted=alert.get("silenced", False),
            last_triggered_at=self._parse_timestamp(alert.get("newStateDate")),
            url=alert.get("url"),
            provider_source=self.provider_name,
        )

    def _rule_to_monitor(self, rule: Dict[str, Any]) -> Monitor:
        """Convert Grafana alert rule to full monitor."""
        state = rule.get("state", "normal")
        labels = rule.get("labels", {})
        annotations = rule.get("annotations", {})
        
        # Extract query from rule data
        queries = []
        for idx, data in enumerate(rule.get("data", [])):
            if data.get("model"):
                queries.append(MonitorQuery(
                    query_id=data.get("refId", f"q{idx}"),
                    raw_query=str(data.get("model")),
                    metric_names=[],
                ))
        
        return Monitor(
            id=rule.get("uid", ""),
            name=rule.get("title", "Untitled"),
            description=annotations.get("description") or annotations.get("summary"),
            resource=ResourceAttributes(),
            monitor_type=MonitorType.METRIC,
            queries=queries,
            thresholds=[],
            status=self._map_grafana_state(state),
            current_value=None,
            last_evaluated_at=None,
            last_triggered_at=None,
            recent_state_changes=[],
            notifications=[],
            tags=list(labels.keys()),
            priority=OTelTransformer.map_severity(labels.get("severity", "warning")),
            is_muted=rule.get("isPaused", False),
            mute_until=None,
            created_by=None,
            modified_by=None,
            created_at=None,
            modified_at=self._parse_timestamp(rule.get("updated")),
            url=None,
            provider_source=self.provider_name,
            provider_monitor_type="alert_rule",
            provider_metadata={
                "condition": rule.get("condition"),
                "no_data_state": rule.get("noDataState"),
                "exec_err_state": rule.get("execErrState"),
                "for": rule.get("for"),
                "folder_uid": rule.get("folderUID"),
                "rule_group": rule.get("ruleGroup"),
            },
        )

    def _map_grafana_state(self, state: str) -> MonitorStatus:
        """Map Grafana alert state to MonitorStatus."""
        state_lower = state.lower()
        if state_lower in ("ok", "normal", "inactive"):
            return MonitorStatus.OK
        elif state_lower in ("pending",):
            return MonitorStatus.WARNING
        elif state_lower in ("alerting", "firing"):
            return MonitorStatus.ALERT
        elif state_lower in ("no_data", "nodata"):
            return MonitorStatus.NO_DATA
        elif state_lower in ("paused",):
            return MonitorStatus.MUTED
        else:
            return MonitorStatus.UNKNOWN

    # ==================== Metrics Methods ====================

    async def query_metrics(self, query: MetricQuery) -> MetricQueryResult:
        """
        Query metrics through Grafana's datasource proxy.
        
        Note: This requires knowing the datasource configuration.
        For direct metrics querying, use Prometheus adapter instead.
        """
        try:
            self._log_request("query_metrics")
            
            # Get list of datasources to find a suitable one
            datasources = await self.client.list_datasources()
            
            # Find Prometheus datasource if available
            prometheus_ds = None
            for ds in datasources:
                if ds.get("type") == "prometheus":
                    prometheus_ds = ds
                    break
            
            if not prometheus_ds:
                # Return empty result if no suitable datasource
                return MetricQueryResult(
                    metrics=[],
                    query=query,
                    total_count=0,
                    query_time_ms=0,
                    providers_queried=[self.provider_name],
                )
            
            # Build query for Prometheus datasource
            promql = self._build_promql_query(query)
            
            start_time = datetime.now(timezone.utc)
            
            # Query through Grafana's datasource proxy
            response = await self.client.query_datasource(
                datasource_uid=prometheus_ds.get("uid"),
                queries=[{
                    "refId": "A",
                    "expr": promql,
                    "datasource": {"uid": prometheus_ds.get("uid")},
                    "intervalMs": (query.step_seconds or 60) * 1000,
                }],
                from_time=query.start_time.isoformat(),
                to_time=query.end_time.isoformat(),
            )
            
            query_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            metrics = self._parse_query_response(response)
            
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
        """Build PromQL-style query from universal query."""
        if query.metric_names:
            metric = query.metric_names[0]
            
            # Build label matchers
            matchers = []
            for key, value in query.attribute_filters.items():
                matchers.append(f'{key}="{value}"')
            
            matcher_str = "{" + ",".join(matchers) + "}" if matchers else ""
            return f"{metric}{matcher_str}"
        
        return query.metric_name_pattern or "up"

    def _parse_query_response(self, response: Dict[str, Any]) -> List[Metric]:
        """Parse Grafana query response to universal format."""
        metrics = []
        
        results = response.get("results", {})
        for ref_id, result in results.items():
            frames = result.get("frames", [])
            
            for frame in frames:
                schema = frame.get("schema", {})
                fields = schema.get("fields", [])
                data = frame.get("data", {})
                values = data.get("values", [])
                
                # Find time and value fields
                time_values = []
                metric_values = []
                metric_name = "unknown"
                labels = {}
                
                for idx, field in enumerate(fields):
                    field_type = field.get("type")
                    field_name = field.get("name", "")
                    
                    if field_type == "time" and idx < len(values):
                        time_values = values[idx]
                    elif field_type in ("number", "float64") and idx < len(values):
                        metric_values = values[idx]
                        metric_name = field_name
                        labels = field.get("labels", {})
                
                # Build data points
                data_points = []
                for i in range(min(len(time_values), len(metric_values))):
                    ts = time_values[i]
                    val = metric_values[i]
                    
                    # Grafana returns milliseconds
                    if isinstance(ts, (int, float)) and ts > 1e12:
                        ts = ts / 1000
                    
                    data_points.append(MetricDataPoint(
                        time=datetime.fromtimestamp(ts, tz=timezone.utc),
                        value=val if val is not None else 0,
                        attributes=labels,
                    ))
                
                if data_points:
                    metrics.append(Metric(
                        name=OTelTransformer.normalize_metric_name(metric_name, "grafana"),
                        description=None,
                        unit=None,
                        metric_type=MetricType.GAUGE,
                        data_points=data_points,
                        resource=self._build_resource_from_labels(labels),
                        provider_source=self.provider_name,
                        provider_metadata={
                            "original_name": metric_name,
                            "ref_id": ref_id,
                        },
                    ))
        
        return metrics

    async def get_metric_metadata(
        self,
        metric_names: Optional[List[str]] = None,
        limit: int = 100,
    ) -> MetricMetadataList:
        """
        Get metric metadata from Grafana.
        
        Note: Grafana doesn't have direct metric metadata API.
        This returns datasource information instead.
        """
        try:
            self._log_request("get_metric_metadata")
            
            # Get list of datasources
            datasources = await self.client.list_datasources()
            
            # Return datasource info as metadata
            metadata = []
            for ds in datasources[:limit]:
                metadata.append(MetricMetadata(
                    name=f"datasource.{ds.get('name', 'unknown')}",
                    description=f"Grafana datasource: {ds.get('type')}",
                    unit=None,
                    metric_type=MetricType.GAUGE,
                    available_attributes=["datasource_type", "datasource_uid"],
                    provider_source=self.provider_name,
                    help_text=f"Datasource of type {ds.get('type')} at {ds.get('url', 'N/A')}",
                ))
            
            return MetricMetadataList(
                metrics=metadata,
                total_count=len(metadata),
                providers_queried=[self.provider_name],
            )
        except Exception as e:
            self._handle_error("get_metric_metadata", e)
            raise AdapterQueryError(str(e), self.provider_name)

    # ==================== Helper Methods ====================

    def _build_resource_from_labels(self, labels: Dict[str, str]) -> ResourceAttributes:
        """Build resource attributes from Grafana labels."""
        return ResourceAttributes(
            service_name=labels.get("job") or labels.get("service"),
            service_instance_id=labels.get("instance"),
            deployment_environment=labels.get("env") or labels.get("environment"),
            custom={k: v for k, v in labels.items()},
        )

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
        """Check Grafana health."""
        try:
            result = await self.client.health()
            return result.get("database") == "ok"
        except Exception:
            return False


# Register adapter with factory
AdapterFactory.register(ProviderType.GRAFANA, GrafanaAdapter)
