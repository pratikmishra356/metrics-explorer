"""Datadog adapter implementation for transforming Datadog data to OTel format."""

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
from app.adapters.datadog.client import DatadogClient
from app.models.dashboard import (
    Dashboard,
    DashboardList,
    DashboardSummary,
    DashboardWidget,
    DashboardWidgetQuery,
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


class DatadogAdapter(BaseAdapter):
    """Adapter for Datadog metrics, dashboards, and monitors."""

    def __init__(
        self,
        provider_config: OrganizationProvider,
        credentials: Dict[str, Any],
    ):
        super().__init__(provider_config, credentials)
        
        self.client = DatadogClient(
            api_key=credentials.get("api_key", ""),
            app_key=credentials.get("app_key", ""),
            site=credentials.get("site", "datadoghq.com"),
            timeout=self.config.timeout_seconds,
        )

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DATADOG

    # ==================== Dashboard Methods ====================

    async def list_dashboards(
        self,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DashboardList:
        """List Datadog dashboards."""
        try:
            self._log_request("list_dashboards")
            response = await self.client.list_dashboards()
            
            dashboards = response.get("dashboards", [])
            
            # Filter by tags if provided
            if tags:
                dashboards = [
                    d for d in dashboards
                    if any(t in d.get("tags", []) for t in tags)
                ]
            
            # Apply pagination
            total = len(dashboards)
            dashboards = dashboards[offset:offset + limit]
            
            summaries = [
                self._to_dashboard_summary(d)
                for d in dashboards
            ]
            
            return DashboardList(
                dashboards=summaries,
                total_count=total,
                providers_queried=[self.provider_name],
            )
        except Exception as e:
            self._handle_error("list_dashboards", e)
            raise AdapterQueryError(str(e), self.provider_name)

    async def get_dashboard(self, dashboard_id: str) -> Dashboard:
        """Get detailed Datadog dashboard."""
        import httpx
        
        try:
            self._log_request("get_dashboard", dashboard_id=dashboard_id)
            response = await self.client.get_dashboard(dashboard_id)
            return self._to_dashboard(response)
        except httpx.HTTPStatusError as e:
            if e.response and e.response.status_code == 404:
                raise AdapterNotFoundError(
                    f"Dashboard not found: {dashboard_id}",
                    self.provider_name,
                )
            self._handle_error("get_dashboard", e)
            raise AdapterQueryError(
                f"HTTP {e.response.status_code if e.response else 'unknown'}: {str(e)}",
                self.provider_name,
            )
        except AdapterNotFoundError:
            # Re-raise as-is
            raise
        except Exception as e:
            self._handle_error("get_dashboard", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _to_dashboard_summary(self, data: Dict[str, Any]) -> DashboardSummary:
        """Convert Datadog dashboard to summary."""
        return DashboardSummary(
            id=data.get("id", ""),
            title=data.get("title", "Untitled"),
            description=data.get("description"),
            tags=data.get("tags", []),
            folder=None,  # Datadog doesn't have folders
            widget_count=0,  # Not available in list
            created_at=self._parse_timestamp(data.get("created_at")),
            modified_at=self._parse_timestamp(data.get("modified_at")),
            url=data.get("url"),
            provider_source=self.provider_name,
        )

    def _to_dashboard(self, data: Dict[str, Any]) -> Dashboard:
        """Convert Datadog dashboard to universal format."""
        widgets = [
            self._to_widget(w, idx)
            for idx, w in enumerate(data.get("widgets", []))
        ]
        
        return Dashboard(
            id=data.get("id", ""),
            title=data.get("title", "Untitled"),
            description=data.get("description"),
            resource=ResourceAttributes(),
            widgets=widgets,
            tags=data.get("tags", []),
            folder=None,
            default_time_range=None,
            refresh_interval=None,
            created_by=data.get("author_handle"),
            modified_by=data.get("modified_by"),
            created_at=self._parse_timestamp(data.get("created_at")),
            modified_at=self._parse_timestamp(data.get("modified_at")),
            url=data.get("url"),
            provider_source=self.provider_name,
            provider_dashboard_type=data.get("layout_type"),
            provider_metadata={
                "layout_type": data.get("layout_type"),
                "is_read_only": data.get("is_read_only"),
                "notify_list": data.get("notify_list"),
                # Preserve template variable definitions from Datadog
                "template_variables": data.get("template_variables", []),
                "template_variable_presets": data.get("template_variable_presets", []),
            },
        )

    def _to_widget(self, data: Dict[str, Any], index: int) -> DashboardWidget:
        """Convert Datadog widget to universal format."""
        definition = data.get("definition", {})
        widget_type = definition.get("type", "unknown")
        
        # Extract queries from widget definition
        queries = self._extract_widget_queries(definition)
        
        # Get layout info
        layout = data.get("layout", {})
        
        return DashboardWidget(
            id=str(data.get("id", index)),
            title=definition.get("title", ""),
            description=None,
            widget_type=OTelTransformer.map_widget_type(widget_type, "datadog"),
            visualization_type=None,
            position={
                "x": layout.get("x", 0),
                "y": layout.get("y", 0),
                "width": layout.get("width", 4),
                "height": layout.get("height", 2),
            },
            queries=queries,
            time_range=definition.get("time"),
            thresholds=[],
            provider_widget_type=widget_type,
            provider_metadata=definition,
        )

    def _extract_widget_queries(
        self, definition: Dict[str, Any]
    ) -> List[DashboardWidgetQuery]:
        """Extract queries from Datadog widget definition."""
        queries = []
        
        # Handle different query locations in Datadog widgets
        requests = definition.get("requests", [])
        if isinstance(requests, list):
            for idx, req in enumerate(requests):
                if isinstance(req, dict):
                    q = req.get("q") or req.get("query")
                    
                    # Handle different query formats - can be string or dict
                    if isinstance(q, dict):
                        # Modern Datadog API format - queries can be objects
                        query_str = q.get("query") or q.get("q") or str(q)
                        # Also check for formulas and function queries
                        if "formulas" in req or "queries" in req:
                            # This is a formulas and functions query - extract from queries array
                            query_objs = req.get("queries", [])
                            if query_objs:
                                # Extract query strings from query objects
                                query_parts = []
                                for q_obj in query_objs:
                                    if isinstance(q_obj, dict):
                                        q_str = q_obj.get("query") or q_obj.get("q") or str(q_obj)
                                        if isinstance(q_str, str):
                                            query_parts.append(q_str)
                                query_str = " ".join(query_parts) if query_parts else str(q)
                            else:
                                query_str = str(q)
                    elif isinstance(q, str):
                        query_str = q
                    else:
                        query_str = str(q) if q else ""
                    
                    if query_str:
                        queries.append(DashboardWidgetQuery(
                            query_id=f"q{idx}",
                            raw_query=query_str,
                            metric_names=self._extract_metric_names(query_str),
                            display_name=req.get("display_type"),
                        ))
        
        return queries

    def _extract_metric_names(self, query: Any) -> List[str]:
        """Extract metric names from Datadog query."""
        # Handle both string and dict inputs
        if isinstance(query, dict):
            # Try to extract query string from dict
            query_str = query.get("query") or query.get("q") or str(query)
        elif isinstance(query, str):
            query_str = query
        else:
            query_str = str(query)
        
        # Simple extraction - looks for patterns like metric_name{...}
        import re
        pattern = r'([a-zA-Z][a-zA-Z0-9_.]+)\{'
        matches = re.findall(pattern, query_str)
        return list(set(matches))

    # ==================== Monitor Methods ====================

    async def list_monitors(
        self,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> MonitorList:
        """List Datadog monitors."""
        try:
            self._log_request("list_monitors")
            page = offset // limit
            monitors = await self.client.list_monitors(tags=tags, page=page, page_size=limit)
            
            # Filter by status if provided
            if status:
                monitors = [
                    m for m in monitors
                    if m.get("overall_state", "").lower() == status.lower()
                ]
            
            summaries = [self._to_monitor_summary(m) for m in monitors]
            
            # Calculate status counts
            status_counts = {}
            for m in monitors:
                state = m.get("overall_state", "unknown").lower()
                status_counts[state] = status_counts.get(state, 0) + 1
            
            return MonitorList(
                monitors=summaries,
                total_count=len(monitors),
                providers_queried=[self.provider_name],
                status_counts=status_counts,
            )
        except Exception as e:
            self._handle_error("list_monitors", e)
            raise AdapterQueryError(str(e), self.provider_name)

    async def get_monitor(self, monitor_id: str) -> Monitor:
        """Get detailed Datadog monitor."""
        try:
            self._log_request("get_monitor", monitor_id=monitor_id)
            response = await self.client.get_monitor(int(monitor_id))
            return self._to_monitor(response)
        except Exception as e:
            if "404" in str(e):
                raise AdapterNotFoundError(
                    f"Monitor not found: {monitor_id}",
                    self.provider_name,
                )
            self._handle_error("get_monitor", e)
            raise AdapterQueryError(str(e), self.provider_name)

    def _to_monitor_summary(self, data: Dict[str, Any]) -> MonitorSummary:
        """Convert Datadog monitor to summary."""
        return MonitorSummary(
            id=str(data.get("id", "")),
            name=data.get("name", "Untitled"),
            description=data.get("message"),
            monitor_type=OTelTransformer.map_monitor_type(
                data.get("type", "metric alert"), "datadog"
            ),
            status=OTelTransformer.map_monitor_status(
                data.get("overall_state", "unknown"), "datadog"
            ),
            priority=OTelTransformer.map_severity(
                str(data.get("priority", "3"))
            ) if data.get("priority") else None,
            tags=data.get("tags", []),
            is_muted=data.get("overall_state") == "Muted",
            last_triggered_at=None,
            url=None,
            provider_source=self.provider_name,
        )

    def _to_monitor(self, data: Dict[str, Any]) -> Monitor:
        """Convert Datadog monitor to universal format."""
        # Extract query from monitor
        query_str = data.get("query", "")
        queries = [
            MonitorQuery(
                query_id="main",
                raw_query=query_str,
                metric_names=self._extract_metric_names(query_str),
            )
        ] if query_str else []
        
        # Extract thresholds
        thresholds = self._extract_monitor_thresholds(data.get("options", {}))
        
        return Monitor(
            id=str(data.get("id", "")),
            name=data.get("name", "Untitled"),
            description=data.get("message"),
            resource=ResourceAttributes(),
            monitor_type=OTelTransformer.map_monitor_type(
                data.get("type", "metric alert"), "datadog"
            ),
            queries=queries,
            thresholds=thresholds,
            status=OTelTransformer.map_monitor_status(
                data.get("overall_state", "unknown"), "datadog"
            ),
            current_value=None,
            last_evaluated_at=None,
            last_triggered_at=None,
            recent_state_changes=[],
            notifications=[],
            tags=data.get("tags", []),
            priority=OTelTransformer.map_severity(
                str(data.get("priority", "3"))
            ) if data.get("priority") else None,
            is_muted=data.get("overall_state") == "Muted",
            mute_until=None,
            created_by=data.get("creator", {}).get("handle"),
            modified_by=None,
            created_at=self._parse_timestamp(data.get("created")),
            modified_at=self._parse_timestamp(data.get("modified")),
            url=None,
            provider_source=self.provider_name,
            provider_monitor_type=data.get("type"),
            provider_metadata={
                "options": data.get("options"),
                "multi": data.get("multi"),
            },
        )

    def _extract_monitor_thresholds(
        self, options: Dict[str, Any]
    ) -> List[MonitorThreshold]:
        """Extract thresholds from Datadog monitor options."""
        thresholds = []
        threshold_data = options.get("thresholds", {})
        
        if "critical" in threshold_data:
            thresholds.append(MonitorThreshold(
                comparison=">",
                value=threshold_data["critical"],
                severity=OTelTransformer.map_severity("critical"),
            ))
        if "warning" in threshold_data:
            thresholds.append(MonitorThreshold(
                comparison=">",
                value=threshold_data["warning"],
                severity=OTelTransformer.map_severity("warning"),
            ))
        
        return thresholds

    # ==================== Metrics Methods ====================

    async def query_metrics(self, query: MetricQuery) -> MetricQueryResult:
        """Query Datadog metrics."""
        try:
            self._log_request("query_metrics")
            
            start_ts = int(query.start_time.timestamp())
            end_ts = int(query.end_time.timestamp())
            
            # Build Datadog query
            metric_query = self._build_datadog_query(query)
            
            start_time = datetime.now(timezone.utc)
            response = await self.client.query_metrics(metric_query, start_ts, end_ts)
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

    def _build_datadog_query(self, query: MetricQuery) -> str:
        """Build Datadog query from universal query."""
        if query.metric_names:
            # Simple metric query
            metric = query.metric_names[0]
            agg = query.aggregation or "avg"
            
            # Build filter from attribute filters
            filters = []
            for key, value in query.attribute_filters.items():
                filters.append(f"{key}:{value}")
            
            filter_str = "{" + ",".join(filters) + "}" if filters else "{*}"
            
            # Build group by
            group_by = ",".join(query.group_by) if query.group_by else ""
            by_clause = f" by {{{group_by}}}" if group_by else ""
            
            return f"{agg}:{metric}{filter_str}{by_clause}"
        
        return query.metric_name_pattern or "*"

    def _parse_metrics_response(self, response: Dict[str, Any]) -> List[Metric]:
        """Parse Datadog metrics response to universal format."""
        metrics = []
        
        for series in response.get("series", []):
            metric_name = series.get("metric", "unknown")
            
            data_points = []
            pointlist = series.get("pointlist", [])
            for point in pointlist:
                if len(point) >= 2:
                    timestamp_ms = point[0]
                    value = point[1]
                    
                    data_points.append(MetricDataPoint(
                        time=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
                        value=value if value is not None else 0,
                        attributes=self._parse_scope(series.get("scope", "")),
                    ))
            
            metrics.append(Metric(
                name=OTelTransformer.normalize_metric_name(metric_name, "datadog"),
                description=None,
                unit=series.get("unit", [{}])[0].get("name") if series.get("unit") else None,
                metric_type=MetricType.GAUGE,
                data_points=data_points,
                resource=self._build_resource_from_tags(series.get("tag_set", [])),
                provider_source=self.provider_name,
                provider_metadata={
                    "original_name": metric_name,
                    "expression": series.get("expression"),
                    "display_name": series.get("display_name"),
                },
            ))
        
        return metrics

    def _parse_scope(self, scope: str) -> Dict[str, Any]:
        """Parse Datadog scope string to attributes."""
        if not scope or scope == "*":
            return {}
        
        attributes = {}
        parts = scope.split(",")
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                attributes[OTelTransformer.normalize_attribute_key(key)] = value
        
        return attributes

    def _build_resource_from_tags(self, tags: List[str]) -> ResourceAttributes:
        """Build resource attributes from Datadog tags."""
        custom = {}
        service_name = None
        environment = None
        host_name = None
        
        for tag in tags:
            if ":" in tag:
                key, value = tag.split(":", 1)
                if key in ("service", "app"):
                    service_name = value
                elif key in ("env", "environment"):
                    environment = value
                elif key == "host":
                    host_name = value
                else:
                    custom[key] = value
        
        return ResourceAttributes(
            service_name=service_name,
            deployment_environment=environment,
            host_name=host_name,
            custom=custom,
        )

    async def get_metric_metadata(
        self,
        metric_names: Optional[List[str]] = None,
        limit: int = 100,
    ) -> MetricMetadataList:
        """Get Datadog metric metadata."""
        try:
            self._log_request("get_metric_metadata")
            
            # Get list of active metrics
            from_ts = int((datetime.now(timezone.utc).timestamp()) - 86400)  # Last 24h
            response = await self.client.list_active_metrics(from_ts)
            
            metrics_list = response.get("metrics", [])
            
            # Filter if specific names requested
            if metric_names:
                metrics_list = [m for m in metrics_list if m in metric_names]
            
            # Apply limit
            metrics_list = metrics_list[:limit]
            
            # Build metadata (note: detailed metadata requires per-metric API calls)
            metadata = [
                MetricMetadata(
                    name=OTelTransformer.normalize_metric_name(m, "datadog"),
                    description=None,
                    unit=None,
                    metric_type=MetricType.GAUGE,
                    available_attributes=[],
                    provider_source=self.provider_name,
                )
                for m in metrics_list
            ]
            
            return MetricMetadataList(
                metrics=metadata,
                total_count=len(metadata),
                providers_queried=[self.provider_name],
            )
        except Exception as e:
            self._handle_error("get_metric_metadata", e)
            raise AdapterQueryError(str(e), self.provider_name)

    # ==================== Template Variable Resolution ====================

    async def resolve_template_variables(
        self,
        template_variables: List[Dict[str, Any]],
        dashboard_metrics: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Resolve Datadog template variable definitions to their possible values.

        Resolution strategy (in priority order):
        1. ``available_values`` from the dashboard definition (user-curated list)
        2. Host tags from ``GET /api/v1/tags/hosts``
        3. **Metric tag fallback** — for variables not found in host tags,
           query one of the dashboard's own metrics grouped by the tag key
           to discover the possible values.

        Args:
            template_variables: Datadog template variable list from dashboard JSON.
            dashboard_metrics: Optional list of metric names used in this dashboard's
                widgets, used for the metric-tag fallback.

        Returns:
            Dict keyed by variable name with resolved values.
        """
        if not template_variables:
            return {}

        # 1. Fetch all host tags in one API call
        try:
            host_tags_response = await self.client.list_host_tags()
            raw_tags = host_tags_response.get("tags", {})
        except Exception as e:
            logger.warning("Failed to fetch host tags for variable resolution", error=str(e))
            raw_tags = {}

        # 2. Build structured map: tag_key -> set(values)
        structured: Dict[str, set] = {}
        for tag_kv in raw_tags.keys():
            tag_kv = tag_kv.strip()
            if not tag_kv:
                continue
            if ":" in tag_kv:
                key, value = tag_kv.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key:
                    if key not in structured:
                        structured[key] = set()
                    if value:
                        structured[key].add(value)

        # 3. Resolve each template variable
        resolved: Dict[str, Dict[str, Any]] = {}
        # Track variables that need the metric-tag fallback
        unresolved_vars: List[Dict[str, Any]] = []

        for var in template_variables:
            name = var.get("name", "")
            if not name:
                continue
            prefix = var.get("prefix") or name  # prefix is the tag key in Datadog
            default_val = var.get("default", "*")
            # Datadog may provide available_values already (user-defined subset)
            predefined = var.get("available_values") or []

            logger.debug(
                "Resolving template variable",
                variable_name=name,
                prefix=prefix,
                has_predefined=bool(predefined),
                predefined_count=len(predefined),
            )

            if predefined:
                # User has pre-defined the allowed values — use those
                values = sorted(predefined)
                logger.info(
                    "Using predefined values for template variable",
                    variable=name,
                    value_count=len(values),
                )
            else:
                # Try resolving from host tags
                values = sorted(structured.get(prefix, set()))
                if not values:
                    logger.info(
                        "Variable not found in host tags, will try metric-tag fallback",
                        variable=name,
                        prefix=prefix,
                    )
                    # Defer to metric-tag fallback below
                    unresolved_vars.append(var)

            resolved[name] = {
                "name": name,
                "tag_key": prefix,
                "default": default_val,
                "values": values,
            }

        # 4. Metric-tag fallback: for unresolved variables, query dashboard metrics
        if unresolved_vars and dashboard_metrics:
            await self._resolve_metric_tags(
                unresolved_vars, dashboard_metrics, resolved
            )

        resolved_count = sum(1 for v in resolved.values() if v["values"])
        logger.info(
            "Resolved template variables",
            total_vars=len(resolved),
            resolved_with_values=resolved_count,
            unresolved=len(resolved) - resolved_count,
        )

        return resolved

    async def _resolve_metric_tags(
        self,
        unresolved_vars: List[Dict[str, Any]],
        dashboard_metrics: List[str],
        resolved: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        Fallback: resolve template variables that are metric-level tags
        (not host tags) by querying the dashboard's own metrics.

        For each unresolved variable we try up to 3 of the dashboard metrics
        (queried with ``by {tag_key}``) until we find values.  Results are
        written back into the *resolved* dict in place.

        Args:
            unresolved_vars: Template variable definitions that had no values
                after host-tag resolution.
            dashboard_metrics: Metric names from this dashboard's widgets.
            resolved: The resolved dict to update in place.
        """
        MAX_METRIC_ATTEMPTS = 3  # try at most 3 metrics per variable

        for var in unresolved_vars:
            name = var.get("name", "")
            prefix = var.get("prefix") or name

            logger.info(
                "Attempting metric-tag fallback for variable",
                variable=name,
                tag_key=prefix,
                candidate_metrics_count=len(dashboard_metrics),
            )

            values: List[str] = []
            for metric_name in dashboard_metrics[:MAX_METRIC_ATTEMPTS]:
                values = await self.client.query_tag_values(
                    metric_name=metric_name,
                    tag_key=prefix,
                    lookback_seconds=14400,  # 4 hours
                )
                if values:
                    logger.info(
                        "Metric-tag fallback succeeded",
                        variable=name,
                        metric_used=metric_name,
                        value_count=len(values),
                    )
                    break

            if values:
                resolved[name]["values"] = values
            else:
                logger.warning(
                    "Could not resolve template variable from any source",
                    variable=name,
                    prefix=prefix,
                    sources_tried=["available_values", "host_tags", "metric_query"],
                )

    # ==================== Dashboard Query Execution ====================

    async def execute_queries(
        self,
        request: "DashboardQueryRequest",
        dashboard_id: str,
    ) -> "DashboardQueryResponse":
        """
        Execute a batch of metric queries using Datadog's native query syntax.

        Builds proper Datadog filter strings from the universal request,
        supporting OR-semantics for list filter values and efficient grouping.
        """
        from app.models.query import (
            DashboardQueryRequest,
            DashboardQueryResponse,
            QueryResultItem,
            Series,
            DataPoint,
        )

        overall_start = datetime.now(timezone.utc)
        start_ts, end_ts = request.time_range.resolve()

        results: list[QueryResultItem] = []
        total_series = 0
        total_dp = 0

        for idx, q_item in enumerate(request.queries):
            item_start = datetime.now(timezone.utc)
            try:
                dd_query = self._build_query_from_item(q_item)
                logger.info(
                    "Executing Datadog query",
                    query_index=idx,
                    metric=q_item.metric_name,
                    dd_query=dd_query,
                )

                raw = await self.client.query_metrics(
                    query=dd_query, start=start_ts, end=end_ts
                )

                series_list: list[Series] = []
                dp_count = 0
                for s in raw.get("series", []):
                    # Parse tags from tag_set
                    tags: Dict[str, str] = {}
                    for tag in s.get("tag_set", []):
                        if ":" in tag:
                            k, v = tag.split(":", 1)
                            tags[k] = v

                    # Parse data points
                    dps: list[DataPoint] = []
                    for pt in s.get("pointlist", []):
                        if len(pt) >= 2:
                            dps.append(
                                DataPoint(
                                    timestamp=int(pt[0]),
                                    value=pt[1],
                                )
                            )

                    dp_count += len(dps)

                    # Determine unit
                    unit_info = s.get("unit")
                    unit = None
                    if unit_info and isinstance(unit_info, list) and unit_info:
                        unit = unit_info[0].get("name") if isinstance(unit_info[0], dict) else None

                    series_list.append(
                        Series(
                            scope=s.get("scope", ""),
                            tags=tags,
                            datapoints=dps,
                            unit=unit,
                        )
                    )

                item_time = int(
                    (datetime.now(timezone.utc) - item_start).total_seconds() * 1000
                )
                total_series += len(series_list)
                total_dp += dp_count

                results.append(
                    QueryResultItem(
                        query_index=idx,
                        metric_name=q_item.metric_name,
                        display_name=s.get("display_name") if raw.get("series") else None,
                        expression=dd_query,
                        series=series_list,
                        series_count=len(series_list),
                        datapoint_count=dp_count,
                        query_time_ms=item_time,
                    )
                )

            except Exception as e:
                logger.error(
                    "Datadog query failed",
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
            (datetime.now(timezone.utc) - overall_start).total_seconds() * 1000
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

    def _build_query_from_item(self, item: "MetricQueryItem") -> str:
        """
        Build a native Datadog query string from a ``MetricQueryItem``.

        Handles:
        - Single-value filters:  ``{env:prod}``
        - Multi-value filters (OR):  ``{tablename IN (a, b, c)}``
        - Group-by:  ``by {tablename, env}``
        """
        from app.models.query import MetricQueryItem

        agg = item.aggregation or "avg"
        metric = item.metric_name

        # Build filter clause
        filter_parts: list[str] = []
        for key, value in item.filters.items():
            if isinstance(value, list):
                if len(value) == 1:
                    filter_parts.append(f"{key}:{value[0]}")
                else:
                    # Datadog OR syntax: comma-separated values for same key
                    # e.g. {tablename:table1 OR tablename:table2}
                    # Simpler: {tablename IN (a,b,c)} is not standard DD syntax
                    # Standard approach: use comma-separated values in scope
                    or_clause = " OR ".join(f"{key}:{v}" for v in value)
                    filter_parts.append(f"({or_clause})")
            else:
                if value and value != "*":
                    filter_parts.append(f"{key}:{value}")

        filter_str = "{" + ",".join(filter_parts) + "}" if filter_parts else "{*}"

        # Build group-by clause
        by_clause = ""
        if item.group_by:
            by_clause = f" by {{{','.join(item.group_by)}}}"

        return f"{agg}:{metric}{filter_str}{by_clause}"

    # ==================== Helper Methods ====================

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not value:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(value, tz=timezone.utc)
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        
        return None


# Register adapter with factory
AdapterFactory.register(ProviderType.DATADOG, DatadogAdapter)
