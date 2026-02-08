"""Service for syncing dashboards from providers to database."""

from typing import List
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import DashboardRepository
from app.models.organization import ProviderType
from app.services.organization_service import OrganizationService
from app.services.query_service import QueryService

logger = structlog.get_logger(__name__)


class DashboardSyncService:
    """Service for syncing dashboards from providers to database."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.dashboard_repo = DashboardRepository(session)
        self.org_service = OrganizationService(session)
        self.query_service = QueryService(session)

    async def sync_dashboards(
        self,
        org_id: UUID,
        provider_type: ProviderType | None = None,
    ) -> dict:
        """
        Sync dashboards from all configured providers to database.
        
        Args:
            org_id: Organization ID
            provider_type: Optional filter by provider type
            
        Returns:
            Dictionary with sync results (created, updated, skipped counts)
        """
        logger.info(
            "Starting dashboard sync",
            org_id=str(org_id),
            provider_type=provider_type.value if provider_type else None,
        )
        
        # Get dashboards from providers
        dashboard_list = await self.query_service.list_dashboards(
            org_id=org_id,
            provider_type=provider_type,
            limit=1000,  # Get all dashboards
        )
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        per_provider: dict = {}  # provider -> {created, updated, skipped}

        # Sync each dashboard to database
        for dashboard_summary in dashboard_list.dashboards:
            try:
                # Determine provider type from provider_source
                dash_provider_type = self._get_provider_type_from_source(
                    dashboard_summary.provider_source
                )
                
                if not dash_provider_type:
                    logger.warning(
                        "Could not determine provider type",
                        dashboard_id=dashboard_summary.id,
                        provider_source=dashboard_summary.provider_source,
                    )
                    skipped_count += 1
                    continue

                pkey = dash_provider_type.value
                if pkey not in per_provider:
                    per_provider[pkey] = {"created": 0, "updated": 0, "skipped": 0}

                # Check if dashboard already exists
                existing = await self.dashboard_repo.get_by_provider_id(
                    org_id, dashboard_summary.id, dash_provider_type
                )
                
                if existing:
                    await self.dashboard_repo.create_or_update(
                        org_id=org_id,
                        dashboard_id=dashboard_summary.id,
                        title=dashboard_summary.title,
                        description=dashboard_summary.description,
                        provider_type=dash_provider_type,
                        provider_source=dashboard_summary.provider_source,
                        metadata={
                            "url": dashboard_summary.url,
                            "tags": dashboard_summary.tags or [],
                            "folder": dashboard_summary.folder,
                            "widget_count": dashboard_summary.widget_count,
                        },
                    )
                    updated_count += 1
                    per_provider[pkey]["updated"] += 1
                else:
                    await self.dashboard_repo.create_or_update(
                        org_id=org_id,
                        dashboard_id=dashboard_summary.id,
                        title=dashboard_summary.title,
                        description=dashboard_summary.description,
                        provider_type=dash_provider_type,
                        provider_source=dashboard_summary.provider_source,
                        metadata={
                            "url": dashboard_summary.url,
                            "tags": dashboard_summary.tags or [],
                            "folder": dashboard_summary.folder,
                            "widget_count": dashboard_summary.widget_count,
                        },
                    )
                    created_count += 1
                    per_provider[pkey]["created"] += 1
            except Exception as e:
                logger.error(
                    "Failed to sync dashboard",
                    dashboard_id=dashboard_summary.id,
                    error=str(e),
                )
                skipped_count += 1
        
        await self.session.commit()
        
        result = {
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "total_fetched": len(dashboard_list.dashboards),
            "providers_queried": dashboard_list.providers_queried,
            "per_provider": per_provider,
        }
        
        logger.info(
            "Dashboard sync completed",
            org_id=str(org_id),
            **result,
        )
        
        return result

    def _get_provider_type_from_source(self, provider_source: str | None) -> ProviderType | None:
        """Get ProviderType from provider_source string."""
        if not provider_source:
            return None
        
        provider_source_lower = provider_source.lower()
        if "datadog" in provider_source_lower:
            return ProviderType.DATADOG
        elif "prometheus" in provider_source_lower:
            return ProviderType.PROMETHEUS
        elif "grafana" in provider_source_lower:
            return ProviderType.GRAFANA
        
        return None
