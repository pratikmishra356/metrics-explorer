"""Query service for routing requests to provider adapters and aggregating responses."""

import asyncio
import structlog
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterFactory, BaseAdapter, AdapterError
from app.models.dashboard import Dashboard, DashboardList, DashboardSummary
from app.models.metrics import (
    MetricMetadataList,
    MetricQuery,
    MetricQueryResult,
)
from app.models.monitor import MonitorList, Monitor
from app.models.organization import OrganizationProvider, ProviderType
from app.services.organization_service import (
    OrganizationService,
    OrganizationNotFoundError,
)

logger = structlog.get_logger(__name__)


class QueryServiceError(Exception):
    """Base exception for query service errors."""
    pass


class QueryService:
    """
    Service for routing queries to appropriate provider adapters
    and aggregating responses.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_service = OrganizationService(session)
        self._adapters: Dict[str, BaseAdapter] = {}

    async def _get_adapters_for_org(
        self,
        org_id: UUID,
        provider_type: Optional[ProviderType] = None,
    ) -> List[Tuple[OrganizationProvider, BaseAdapter]]:
        """
        Get configured adapters for an organization.
        
        Args:
            org_id: Organization ID
            provider_type: Optional filter by provider type
            
        Returns:
            List of (provider_config, adapter) tuples
        """
        providers = await self.org_service.get_providers_for_organization(
            org_id, provider_type
        )
        
        logger.info(
            "Found providers for organization",
            org_id=str(org_id),
            provider_count=len(providers),
            providers=[f"{p.provider_type.value}:{p.name}" for p in providers],
        )
        
        adapters = []
        for provider in providers:
            try:
                logger.debug(
                    "Creating adapter",
                    org_id=str(org_id),
                    provider_type=provider.provider_type.value,
                    provider_name=provider.name,
                )
                # Get credentials and create adapter
                _, credentials = await self.org_service.get_provider_with_credentials(
                    org_id,
                    provider.provider_type,
                    provider.name,
                )
                
                logger.debug(
                    "Got credentials, creating adapter",
                    provider_type=provider.provider_type.value,
                    has_credentials=bool(credentials),
                )
                
                adapter = AdapterFactory.create(provider, credentials)
                adapters.append((provider, adapter))
                logger.info(
                    "Adapter created successfully",
                    provider_type=provider.provider_type.value,
                    provider_name=provider.name,
                )
            except Exception as e:
                import traceback
                logger.error(
                    "Failed to create adapter",
                    org_id=str(org_id),
                    provider_type=provider.provider_type.value,
                    provider_name=provider.name,
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                )
        
        logger.info(
            "Adapter creation complete",
            org_id=str(org_id),
            adapters_created=len(adapters),
            total_providers=len(providers),
        )
        
        return adapters

    async def _execute_on_adapters(
        self,
        org_id: UUID,
        operation: str,
        provider_type: Optional[ProviderType] = None,
        **kwargs,
    ) -> List[Tuple[str, Any, Optional[Exception]]]:
        """
        Execute an operation on all relevant adapters concurrently.
        
        Args:
            org_id: Organization ID
            operation: Method name to call on adapters
            provider_type: Optional filter by provider type
            **kwargs: Arguments to pass to the operation
            
        Returns:
            List of (provider_name, result, error) tuples
        """
        adapters = await self._get_adapters_for_org(org_id, provider_type)
        
        if not adapters:
            logger.warning(
                "No adapters available for organization",
                org_id=str(org_id),
                provider_type=provider_type.value if provider_type else None,
            )
            # Log more details about why no adapters were found
            try:
                org_service = OrganizationService(self.session)
                providers = await org_service.get_providers_for_organization(org_id)
                logger.info(
                    "Organization providers",
                    org_id=str(org_id),
                    provider_count=len(providers),
                    providers=[p.provider_type.value for p in providers],
                )
            except Exception as e:
                logger.error("Failed to fetch organization providers", error=str(e))
            return []
        
        async def execute_one(
            provider: OrganizationProvider, adapter: BaseAdapter
        ) -> Tuple[str, Any, Optional[Exception]]:
            from app.adapters.base import AdapterNotFoundError
            
            provider_name = provider.provider_type.value
            try:
                logger.info(
                    f"Executing adapter operation: {operation}",
                    provider=provider_name,
                    operation=operation,
                    kwargs_keys=list(kwargs.keys()),
                )
                method = getattr(adapter, operation)
                result = await method(**kwargs)
                logger.info(
                    f"Adapter operation succeeded: {operation}",
                    provider=provider_name,
                )
                return (provider_name, result, None)
            except AdapterNotFoundError as e:
                # Don't log as error for not found - it's expected when searching
                logger.debug(
                    f"Resource not found: {operation}",
                    provider=provider_name,
                    error=str(e),
                )
                return (provider_name, None, e)
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                logger.error(
                    f"Adapter operation failed: {operation}",
                    provider=provider_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=error_trace,
                )
                return (provider_name, None, e)
        
        # Execute concurrently
        tasks = [execute_one(p, a) for p, a in adapters]
        results = await asyncio.gather(*tasks)
        
        return results

    # ==================== Dashboard Methods ====================

    async def list_dashboards(
        self,
        org_id: UUID,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        provider_type: Optional[ProviderType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DashboardList:
        """
        List dashboards from all configured providers.
        
        Args:
            org_id: Organization ID
            tags: Optional filter by tags
            folder: Optional filter by folder
            provider_type: Optional filter by provider
            limit: Maximum results per provider
            offset: Offset for pagination
        """
        results = await self._execute_on_adapters(
            org_id,
            "list_dashboards",
            provider_type=provider_type,
            tags=tags,
            folder=folder,
            limit=limit,
            offset=offset,
        )
        
        # Aggregate results
        all_dashboards: List[DashboardSummary] = []
        providers_queried: List[str] = []
        errors: List[str] = []
        
        for provider_name, result, error in results:
            providers_queried.append(provider_name)
            if error:
                error_msg = f"{provider_name}: {str(error)}"
                errors.append(error_msg)
                logger.error(
                    "Provider query failed",
                    provider=provider_name,
                    error=str(error),
                    operation="list_dashboards",
                )
            elif result and isinstance(result, DashboardList):
                all_dashboards.extend(result.dashboards)
        
        if errors and not all_dashboards:
            # If all providers failed, raise an error
            raise QueryServiceError(f"All providers failed: {'; '.join(errors)}")
        
        return DashboardList(
            dashboards=all_dashboards,
            total_count=len(all_dashboards),
            providers_queried=providers_queried,
        )

    async def get_dashboard(
        self,
        org_id: UUID,
        dashboard_id: str,
        provider_type: Optional[ProviderType] = None,
    ) -> Dashboard:
        """
        Get a specific dashboard.
        
        If provider_type is not specified, tries all providers until found.
        """
        from app.adapters.base import AdapterNotFoundError
        
        results = await self._execute_on_adapters(
            org_id,
            "get_dashboard",
            provider_type=provider_type,
            dashboard_id=dashboard_id,
        )
        
        # Return first successful result
        not_found_errors = []
        other_errors = []
        
        for provider_name, result, error in results:
            if result and isinstance(result, Dashboard):
                logger.info(
                    "Dashboard found",
                    dashboard_id=dashboard_id,
                    provider=provider_name,
                )
                return result
            
            if error:
                if isinstance(error, AdapterNotFoundError):
                    not_found_errors.append(f"{provider_name}: {str(error)}")
                else:
                    other_errors.append(f"{provider_name}: {str(error)}")
        
        # If we have not found errors from all providers, raise not found
        if not_found_errors and not other_errors:
            raise QueryServiceError(f"Dashboard not found: {dashboard_id}")
        
        # If we have other errors, raise them
        if other_errors:
            raise QueryServiceError(
                f"Failed to get dashboard {dashboard_id}: {'; '.join(other_errors)}"
            )
        
        # Fallback
        raise QueryServiceError(f"Dashboard not found: {dashboard_id}")

    # ==================== Monitor Methods ====================

    async def list_monitors(
        self,
        org_id: UUID,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        provider_type: Optional[ProviderType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> MonitorList:
        """
        List monitors from all configured providers.
        """
        results = await self._execute_on_adapters(
            org_id,
            "list_monitors",
            provider_type=provider_type,
            tags=tags,
            status=status,
            limit=limit,
            offset=offset,
        )
        
        # Aggregate results
        all_monitors = []
        providers_queried = []
        status_counts: Dict[str, int] = {}
        
        for provider_name, result, error in results:
            providers_queried.append(provider_name)
            if result and isinstance(result, MonitorList):
                all_monitors.extend(result.monitors)
                # Merge status counts
                for status_key, count in result.status_counts.items():
                    status_counts[status_key] = status_counts.get(status_key, 0) + count
        
        return MonitorList(
            monitors=all_monitors,
            total_count=len(all_monitors),
            providers_queried=providers_queried,
            status_counts=status_counts,
        )

    async def get_monitor(
        self,
        org_id: UUID,
        monitor_id: str,
        provider_type: Optional[ProviderType] = None,
    ) -> Monitor:
        """
        Get a specific monitor.
        
        If provider_type is not specified, tries all providers until found.
        """
        results = await self._execute_on_adapters(
            org_id,
            "get_monitor",
            provider_type=provider_type,
            monitor_id=monitor_id,
        )
        
        # Return first successful result
        for provider_name, result, error in results:
            if result and isinstance(result, Monitor):
                return result
        
        # If all failed, raise error
        raise QueryServiceError(f"Monitor not found: {monitor_id}")

    # ==================== Metrics Methods ====================

    async def query_metrics(
        self,
        org_id: UUID,
        query: MetricQuery,
        provider_type: Optional[ProviderType] = None,
    ) -> MetricQueryResult:
        """
        Query metrics from all configured providers.
        """
        start_time = datetime.utcnow()
        
        results = await self._execute_on_adapters(
            org_id,
            "query_metrics",
            provider_type=provider_type,
            query=query,
        )
        
        # Aggregate results
        all_metrics = []
        providers_queried = []
        
        for provider_name, result, error in results:
            providers_queried.append(provider_name)
            if result and isinstance(result, MetricQueryResult):
                all_metrics.extend(result.metrics)
        
        total_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return MetricQueryResult(
            metrics=all_metrics,
            query=query,
            total_count=len(all_metrics),
            query_time_ms=total_time,
            providers_queried=providers_queried,
        )

    async def get_metric_metadata(
        self,
        org_id: UUID,
        metric_names: Optional[List[str]] = None,
        provider_type: Optional[ProviderType] = None,
        limit: int = 100,
    ) -> MetricMetadataList:
        """
        Get metric metadata from all configured providers.
        """
        results = await self._execute_on_adapters(
            org_id,
            "get_metric_metadata",
            provider_type=provider_type,
            metric_names=metric_names,
            limit=limit,
        )
        
        # Aggregate results
        all_metadata = []
        providers_queried = []
        
        for provider_name, result, error in results:
            providers_queried.append(provider_name)
            if result and isinstance(result, MetricMetadataList):
                all_metadata.extend(result.metrics)
        
        return MetricMetadataList(
            metrics=all_metadata,
            total_count=len(all_metadata),
            providers_queried=providers_queried,
        )

    # ==================== Template Variable Resolution ====================

    async def resolve_template_variables(
        self,
        org_id: UUID,
        template_variables: List[Dict[str, Any]],
        provider_type: Optional[ProviderType] = None,
        dashboard_metrics: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Resolve template variable definitions through the appropriate provider adapter.

        Delegates to the first matching adapter (since template variables are
        dashboard-scoped, only one provider is expected).

        Args:
            org_id: Organization ID
            template_variables: Raw template variable definitions from the dashboard
            provider_type: Optional filter by provider type
            dashboard_metrics: Optional list of metric names from dashboard widgets.
                Used as a fallback source for resolving metric-level tags.

        Returns:
            Dict keyed by variable name with resolved values
        """
        try:
            adapters = await self._get_adapters_for_org(org_id, provider_type)
            if not adapters:
                logger.warning("No adapters found for template variable resolution")
                return {}

            # Use the first matching adapter (template vars are provider-specific)
            _provider_config, adapter = adapters[0]
            return await adapter.resolve_template_variables(
                template_variables,
                dashboard_metrics=dashboard_metrics,
            )
        except Exception as e:
            logger.error("Failed to resolve template variables", error=str(e))
            return {}



# Dependency for FastAPI
async def get_query_service(session: AsyncSession) -> QueryService:
    """Dependency to get query service instance."""
    return QueryService(session)
