"""Service for extracting metrics from dashboard detail objects and persisting them."""

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import DashboardRepository, MetricRepository, TemplateVariableRepository
from app.models.dashboard import Dashboard, DashboardWidget
from app.models.organization import ProviderType
from app.services.query_service import QueryService

logger = structlog.get_logger(__name__)


class MetricExtractService:
    """
    Service that fetches a dashboard detail from a provider,
    walks through all widgets (including nested group widgets),
    extracts widget-level metric data, and persists one row per
    widget to the dashboard_metrics table.
    """

    # Maximum number of resolved values before we consider a variable
    # "high cardinality" and skip storing it.
    MAX_VARIABLE_VALUES = 5000

    def __init__(self, session: AsyncSession):
        self.session = session
        self.dashboard_repo = DashboardRepository(session)
        self.metric_repo = MetricRepository(session)
        self.template_var_repo = TemplateVariableRepository(session)
        self.query_service = QueryService(session)

    async def extract_metrics(
        self,
        org_id: UUID,
        provider_dashboard_id: str,
        provider_type: Optional[ProviderType] = None,
    ) -> dict:
        """
        Extract metrics from a dashboard and store them in the database.

        One row per widget — all requests/queries/formulas for a widget
        are bundled into the ``details`` JSON column.

        Template variables defined on the dashboard are resolved once via
        the provider adapter (e.g. a single ``GET /api/v1/tags/hosts`` call
        for Datadog) and then the **used** variables are embedded in each
        widget's ``details.template_variables``.

        Args:
            org_id: Organization ID
            provider_dashboard_id: The provider's dashboard ID (e.g. "9xz-8y3-e5g")
            provider_type: Optional provider type filter

        Returns:
            Dictionary with extraction results (created, updated, total)
        """
        logger.info(
            "Starting metric extraction",
            org_id=str(org_id),
            dashboard_id=provider_dashboard_id,
        )

        # 1. Fetch the full dashboard detail from the provider
        dashboard: Dashboard = await self.query_service.get_dashboard(
            org_id=org_id,
            dashboard_id=provider_dashboard_id,
            provider_type=provider_type,
        )

        # 2. Determine the provider string from the dashboard
        provider_str = self._resolve_provider(dashboard.provider_source)

        # 3. Extract all metric names from the dashboard widgets.
        #    These are needed for the metric-tag fallback when template
        #    variables reference metric-level tags (not host tags).
        dashboard_metric_names = self._extract_all_metric_names(dashboard)

        # 4. Resolve template variables defined on this dashboard
        #    Resolution order: available_values -> host tags -> metric-tag fallback
        raw_template_vars = dashboard.provider_metadata.get("template_variables", [])
        resolved_vars: Dict[str, Dict[str, Any]] = {}
        if raw_template_vars:
            resolved_vars = await self.query_service.resolve_template_variables(
                org_id=org_id,
                template_variables=raw_template_vars,
                provider_type=provider_type,
                dashboard_metrics=dashboard_metric_names,
            )
            logger.info(
                "Template variables resolved",
                total=len(resolved_vars),
                with_values=sum(1 for v in resolved_vars.values() if v.get("values")),
                dashboard_metrics_count=len(dashboard_metric_names),
            )

        # 5. Look up the stored dashboard row to get the DB dashboard_id
        db_dashboard = await self._find_or_create_db_dashboard(
            org_id=org_id,
            provider_dashboard_id=provider_dashboard_id,
            dashboard=dashboard,
            provider_str=provider_str,
        )

        # 6. Persist resolved template variables into the template_variables table
        #    (skip high-cardinality vars with >5 000 values)
        vars_stored = 0
        vars_skipped = 0
        for var_name, var_info in resolved_vars.items():
            values = var_info.get("values", [])
            if len(values) > self.MAX_VARIABLE_VALUES:
                logger.info(
                    "Skipping high-cardinality template variable",
                    variable=var_name,
                    value_count=len(values),
                )
                vars_skipped += 1
                continue
            try:
                await self.template_var_repo.upsert(
                    org_id=org_id,
                    dashboard_id=db_dashboard.id,
                    variable_name=var_name,
                    tag_key=var_info.get("tag_key", var_name),
                    default_value=var_info.get("default"),
                    values=values,
                    provider=provider_str,
                )
                vars_stored += 1
            except Exception as e:
                logger.error(
                    "Failed to store template variable",
                    variable=var_name,
                    error=str(e),
                )

        # 7. Walk widgets and extract one item per widget
        created_count = 0
        updated_count = 0
        widget_items = self._extract_widget_items(dashboard.widgets)

        for item in widget_items:
            try:
                # Store only the *names* of used template variables (not full objects)
                used_var_names = self._find_used_variable_names(
                    item["details"], resolved_vars
                )
                if used_var_names:
                    item["details"]["template_variable_names"] = used_var_names

                result = await self.metric_repo.create_or_update(
                    dashboard_id=db_dashboard.id,
                    provider=provider_str,
                    widget_id=item["widget_id"],
                    name=item["name"],
                    description=item.get("description"),
                    details=item["details"],
                )

                if result.created_at == result.updated_at:
                    created_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                logger.error(
                    "Failed to save metric",
                    widget_id=item.get("widget_id"),
                    error=str(e),
                )

        await self.session.commit()

        result_summary = {
            "created": created_count,
            "updated": updated_count,
            "total": created_count + updated_count,
            "dashboard_id": db_dashboard.id,
            "provider_dashboard_id": provider_dashboard_id,
            "template_variables_stored": vars_stored,
            "template_variables_skipped_high_cardinality": vars_skipped,
        }

        logger.info(
            "Metric extraction completed",
            org_id=str(org_id),
            **result_summary,
        )

        return result_summary

    # ------------------------------------------------------------------ #
    #  Widget traversal — returns one item per widget
    # ------------------------------------------------------------------ #

    def _extract_widget_items(
        self,
        widgets: List[DashboardWidget],
        parent_group_details: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Walk the widget tree and produce one item per leaf widget.

        For group widgets → recurse into children with parent_group_details.
        For leaf widgets  → build a single item containing full widget data.
        """
        items: List[Dict[str, Any]] = []

        for widget in widgets:
            if widget.provider_widget_type == "group":
                group_details = {
                    "group_id": widget.id,
                    "group_title": widget.title,
                    "group_layout_type": widget.provider_metadata.get("layout_type"),
                }

                child_widgets_raw = widget.provider_metadata.get("widgets", [])
                child_items = self._extract_child_widget_items(
                    child_widgets_raw,
                    parent_group_details=group_details,
                )
                items.extend(child_items)
            else:
                item = self._build_widget_item(
                    widget_id=widget.id,
                    widget_definition=widget.provider_metadata,
                    parent_group_details=parent_group_details,
                )
                if item:
                    items.append(item)

        return items

    def _extract_child_widget_items(
        self,
        child_widgets_raw: List[Dict[str, Any]],
        parent_group_details: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract items from raw child widget dicts inside a group's
        provider_metadata (the raw Datadog objects with {id, definition}).
        """
        items: List[Dict[str, Any]] = []

        for child_widget in child_widgets_raw:
            child_id = str(child_widget.get("id", ""))
            definition = child_widget.get("definition", {})

            # A child widget could itself be a nested group (rare)
            if definition.get("type") == "group":
                nested_group_details = {
                    "group_id": child_id,
                    "group_title": definition.get("title", ""),
                    "group_layout_type": definition.get("layout_type"),
                }
                nested_children = definition.get("widgets", [])
                nested_items = self._extract_child_widget_items(
                    nested_children,
                    parent_group_details=nested_group_details,
                )
                items.extend(nested_items)
            else:
                item = self._build_widget_item(
                    widget_id=child_id,
                    widget_definition=definition,
                    parent_group_details=parent_group_details,
                )
                if item:
                    items.append(item)

        return items

    def _build_widget_item(
        self,
        widget_id: str,
        widget_definition: Dict[str, Any],
        parent_group_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Build a single metric item for a leaf widget.

        Bundles all requests/queries/formulas into the `details` JSON.
        Returns None if there is nothing meaningful to store.
        """
        widget_title = widget_definition.get("title", "")
        widget_type = widget_definition.get("type", "")
        requests = widget_definition.get("requests", [])

        if not isinstance(requests, list):
            requests = []

        # Build details object with full widget data
        details: Dict[str, Any] = {
            "widget_title": widget_title,
            "widget_type": widget_type,
            "requests": [],
        }

        for req in requests:
            if not isinstance(req, dict):
                continue
            request_entry: Dict[str, Any] = {}

            # Formulas
            formulas = req.get("formulas", [])
            if formulas:
                request_entry["formulas"] = formulas

            # Queries (modern format)
            queries = req.get("queries", [])
            if isinstance(queries, list) and queries:
                request_entry["queries"] = self._normalize_queries(queries)

            # Simple "q" string (legacy Datadog format)
            simple_q = req.get("q")
            if simple_q and isinstance(simple_q, str) and not queries:
                request_entry["queries"] = [
                    {"query": simple_q, "data_source": "metrics", "name": "q0"}
                ]

            # Other useful fields
            for key in ("response_format", "display_type", "style", "on_right_yaxis"):
                val = req.get(key)
                if val is not None:
                    request_entry[key] = val

            if request_entry:
                details["requests"].append(request_entry)

        # Attach parent group info if this widget is inside a group
        if parent_group_details:
            details["parent_group_details"] = parent_group_details

        # Build the human-readable name: prefer widget title, fall back to
        # a summary of metric names found in the queries
        name = widget_title or self._derive_name_from_details(details)
        description = self._derive_description(details)

        return {
            "widget_id": widget_id,
            "name": name or f"widget-{widget_id}",
            "description": description,
            "details": details,
        }

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _normalize_queries(self, queries: List[Any]) -> List[Dict[str, Any]]:
        """Ensure every query item is a well-formed dict with a 'query' string."""
        normalized: List[Dict[str, Any]] = []
        for q in queries:
            if not isinstance(q, dict):
                continue
            query_str = q.get("query") or q.get("q") or ""
            if isinstance(query_str, dict):
                query_str = query_str.get("query") or str(query_str)
            entry = dict(q)
            entry["query"] = str(query_str)
            normalized.append(entry)
        return normalized

    def _derive_name_from_details(self, details: Dict[str, Any]) -> Optional[str]:
        """Try to build a name from the metric names found in queries."""
        metric_names: List[str] = []
        for req in details.get("requests", []):
            for q in req.get("queries", []):
                query_str = q.get("query", "")
                extracted = self._extract_metric_name(query_str)
                if extracted and extracted not in metric_names:
                    metric_names.append(extracted)
        if metric_names:
            return ", ".join(metric_names[:3])
        return None

    def _derive_description(self, details: Dict[str, Any]) -> Optional[str]:
        """Build a short description from widget type and query count."""
        widget_type = details.get("widget_type", "")
        total_queries = sum(
            len(req.get("queries", [])) for req in details.get("requests", [])
        )
        if widget_type and total_queries:
            return f"{widget_type} widget with {total_queries} quer{'y' if total_queries == 1 else 'ies'}"
        return None

    def _extract_metric_name(self, query: str) -> Optional[str]:
        """Extract the primary metric name from a query string."""
        if not query or not isinstance(query, str):
            return None
        # Pattern: aggregation:metric_name{...}
        pattern = r'(?:avg|sum|min|max|count|p\d+|last):?([a-zA-Z][a-zA-Z0-9_.]+)\{'
        match = re.search(pattern, query)
        if match:
            return match.group(1)
        # Fallback: any metric-like pattern before {
        pattern2 = r'([a-zA-Z][a-zA-Z0-9_.]+)\{'
        match2 = re.search(pattern2, query)
        if match2:
            return match2.group(1)
        return None

    def _find_used_variable_names(
        self,
        details: Dict[str, Any],
        resolved_vars: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """
        Scan the widget's query strings for ``$var_name`` references and
        return a sorted list of variable names that appear in this widget.
        """
        if not resolved_vars:
            return []

        query_strings: List[str] = []
        for req in details.get("requests", []):
            if not isinstance(req, dict):
                continue
            for q in req.get("queries", []):
                if isinstance(q, dict):
                    qs = q.get("query", "")
                    if isinstance(qs, str):
                        query_strings.append(qs)

        if not query_strings:
            return []

        all_text = " ".join(query_strings)

        used: List[str] = []
        for var_name in resolved_vars:
            if f"${var_name}" in all_text or var_name in all_text:
                used.append(var_name)

        return sorted(used)

    def _extract_all_metric_names(self, dashboard: Dashboard) -> List[str]:
        """
        Walk all widgets in the dashboard and extract unique metric names
        from their query strings.

        These names are used by the adapter's metric-tag fallback to query
        for tag values that don't appear in host tags.
        """
        metric_names: List[str] = []

        def _scan_widget(widget: DashboardWidget) -> None:
            for q in widget.queries:
                for name in (q.metric_names or []):
                    if name and name not in metric_names:
                        metric_names.append(name)
            # Also scan raw provider_metadata for nested/group widgets
            raw_widgets = (widget.provider_metadata or {}).get("widgets", [])
            for raw in raw_widgets:
                defn = raw.get("definition", {})
                for req in defn.get("requests", []):
                    if not isinstance(req, dict):
                        continue
                    for q_obj in req.get("queries", []):
                        if isinstance(q_obj, dict):
                            qs = q_obj.get("query", "")
                            extracted = self._extract_metric_name(qs)
                            if extracted and extracted not in metric_names:
                                metric_names.append(extracted)
                    # Legacy "q" field
                    simple_q = req.get("q", "")
                    if isinstance(simple_q, str):
                        extracted = self._extract_metric_name(simple_q)
                        if extracted and extracted not in metric_names:
                            metric_names.append(extracted)

        for widget in dashboard.widgets:
            _scan_widget(widget)

        logger.debug(
            "Extracted metric names from dashboard",
            count=len(metric_names),
            sample=metric_names[:10],
        )
        return metric_names

    def _resolve_provider(self, provider_source: Optional[str]) -> str:
        """Resolve provider string from provider_source."""
        if not provider_source:
            return "unknown"
        lower = provider_source.lower()
        if "datadog" in lower:
            return ProviderType.DATADOG.value
        elif "prometheus" in lower:
            return ProviderType.PROMETHEUS.value
        elif "grafana" in lower:
            return ProviderType.GRAFANA.value
        return provider_source

    async def _find_or_create_db_dashboard(
        self,
        org_id: UUID,
        provider_dashboard_id: str,
        dashboard: Dashboard,
        provider_str: str,
    ):
        """
        Find the stored OrganizationDashboardModel for this provider dashboard.
        If it doesn't exist yet, create it so we have a valid FK target.
        """
        provider_type_map = {
            ProviderType.DATADOG.value: ProviderType.DATADOG,
            ProviderType.PROMETHEUS.value: ProviderType.PROMETHEUS,
            ProviderType.GRAFANA.value: ProviderType.GRAFANA,
        }
        ptype = provider_type_map.get(provider_str)

        if ptype:
            db_dash = await self.dashboard_repo.get_by_provider_id(
                org_id=org_id,
                dashboard_id=provider_dashboard_id,
                provider_type=ptype,
            )
            if db_dash:
                return db_dash

        # Dashboard not found in DB -- create it so we have a FK target
        if not ptype:
            ptype = ProviderType.DATADOG  # fallback

        db_dash = await self.dashboard_repo.create_or_update(
            org_id=org_id,
            dashboard_id=provider_dashboard_id,
            title=dashboard.title,
            description=dashboard.description,
            provider_type=ptype,
            provider_source=dashboard.provider_source,
            metadata={
                "url": dashboard.url,
                "tags": dashboard.tags or [],
            },
        )
        return db_dash
