"""
Service for executing metric queries against provider backends.

Looks up the organisation's provider, delegates to the correct adapter,
and returns a provider-agnostic ``DashboardQueryResponse``.
"""

import structlog
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterFactory, BaseAdapter
from app.db.repositories import DashboardRepository
from app.models.organization import ProviderType
from app.models.query import DashboardQueryRequest, DashboardQueryResponse
from app.services.organization_service import OrganizationService

logger = structlog.get_logger(__name__)


class QueryExecutionError(Exception):
    """Raised when query execution fails."""
    pass


class MetricQueryExecutionService:
    """
    Orchestrates metric query execution for a dashboard.

    1. Resolves the dashboard's provider from the DB.
    2. Creates the appropriate adapter with credentials.
    3. Delegates to ``adapter.execute_queries()``.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_service = OrganizationService(session)
        self.dashboard_repo = DashboardRepository(session)

    async def execute(
        self,
        org_id: UUID,
        dashboard_id: str,
        request: DashboardQueryRequest,
        provider_type: Optional[ProviderType] = None,
    ) -> DashboardQueryResponse:
        """
        Execute metric queries for a dashboard.

        Args:
            org_id: Organisation UUID.
            dashboard_id: Either the internal DB dashboard ID or the provider
                dashboard ID (e.g. ``"4k2-qvg-h38"`` for Datadog).
            request: The batch query request.
            provider_type: Optional explicit provider.  When ``None`` the
                provider is inferred from the stored dashboard row.

        Returns:
            ``DashboardQueryResponse`` with results from the provider.
        """
        # 1. Resolve the provider dashboard ID and type
        provider_dashboard_id, resolved_type = await self._resolve_dashboard(
            org_id, dashboard_id, provider_type
        )

        # 2. Create the adapter
        adapter = await self._get_adapter(org_id, resolved_type)

        logger.info(
            "Executing dashboard queries",
            org_id=str(org_id),
            dashboard_id=provider_dashboard_id,
            provider=resolved_type.value,
            query_count=len(request.queries),
            time_range=str(request.time_range),
        )

        # 3. Delegate to the adapter
        try:
            return await adapter.execute_queries(request, provider_dashboard_id)
        except Exception as e:
            logger.error(
                "Query execution failed",
                org_id=str(org_id),
                dashboard_id=provider_dashboard_id,
                error=str(e),
            )
            raise QueryExecutionError(
                f"Failed to execute queries: {e}"
            ) from e

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    async def _resolve_dashboard(
        self,
        org_id: UUID,
        dashboard_id: str,
        provider_type: Optional[ProviderType],
    ) -> tuple[str, ProviderType]:
        """
        Determine the provider dashboard ID and provider type.

        If ``dashboard_id`` matches a stored DB row, we extract
        ``dashboard_id`` (the provider ID) and ``provider_type`` from
        the row.  Otherwise we treat it as the raw provider ID and
        require ``provider_type`` to be given (or default to Datadog).
        """
        # Try DB lookup first
        db_dash = await self.dashboard_repo.get_by_id(dashboard_id)
        if db_dash:
            ptype = ProviderType(db_dash.provider_type) if db_dash.provider_type else (provider_type or ProviderType.DATADOG)
            return db_dash.dashboard_id, ptype

        # Fallback: treat as provider dashboard ID
        if provider_type:
            return dashboard_id, provider_type

        # Try to find it via provider ID search across types
        for ptype in ProviderType:
            db_dash = await self.dashboard_repo.get_by_provider_id(
                org_id=org_id, dashboard_id=dashboard_id, provider_type=ptype
            )
            if db_dash:
                return dashboard_id, ptype

        # Last resort: Datadog
        logger.warning(
            "Could not resolve dashboard provider, defaulting to Datadog",
            dashboard_id=dashboard_id,
        )
        return dashboard_id, ProviderType.DATADOG

    async def _get_adapter(
        self,
        org_id: UUID,
        provider_type: ProviderType,
    ) -> BaseAdapter:
        """Create an adapter with decrypted credentials."""
        provider_config, credentials = await self.org_service.get_provider_with_credentials(
            org_id, provider_type
        )
        return AdapterFactory.create(provider_config, credentials)
