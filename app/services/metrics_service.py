"""Metrics service for higher-level metrics operations."""

import structlog
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import (
    MetricMetadataList,
    MetricQuery,
    MetricQueryResult,
)
from app.models.organization import ProviderType
from app.services.query_service import QueryService

logger = structlog.get_logger(__name__)


class MetricsService:
    """
    Higher-level service for metrics operations.
    
    Provides convenient methods for common metrics queries
    and operations on top of the QueryService.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.query_service = QueryService(session)

    async def query_metrics(
        self,
        org_id: UUID,
        query: MetricQuery,
        provider_type: Optional[ProviderType] = None,
    ) -> MetricQueryResult:
        """
        Query metrics with the given parameters.
        
        Delegates to QueryService for actual execution.
        """
        return await self.query_service.query_metrics(
            org_id=org_id,
            query=query,
            provider_type=provider_type,
        )

    async def query_metrics_simple(
        self,
        org_id: UUID,
        metric_names: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        step_seconds: int = 60,
        filters: Optional[dict] = None,
        aggregation: Optional[str] = None,
        group_by: Optional[List[str]] = None,
        provider_type: Optional[ProviderType] = None,
    ) -> MetricQueryResult:
        """
        Simplified metrics query interface.
        
        Args:
            org_id: Organization ID
            metric_names: List of metric names to query
            start_time: Query start time (default: 1 hour ago)
            end_time: Query end time (default: now)
            step_seconds: Step interval in seconds
            filters: Attribute filters as key-value pairs
            aggregation: Aggregation function (avg, sum, min, max, count)
            group_by: Attributes to group by
            provider_type: Optional provider filter
        """
        # Set default time range
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(hours=1)
        
        query = MetricQuery(
            metric_names=metric_names,
            start_time=start_time,
            end_time=end_time,
            step_seconds=step_seconds,
            attribute_filters=filters or {},
            aggregation=aggregation,
            group_by=group_by or [],
        )
        
        return await self.query_service.query_metrics(
            org_id=org_id,
            query=query,
            provider_type=provider_type,
        )

    async def get_metric_metadata(
        self,
        org_id: UUID,
        metric_names: Optional[List[str]] = None,
        provider_type: Optional[ProviderType] = None,
        limit: int = 100,
    ) -> MetricMetadataList:
        """
        Get metadata for available metrics.
        """
        return await self.query_service.get_metric_metadata(
            org_id=org_id,
            metric_names=metric_names,
            provider_type=provider_type,
            limit=limit,
        )

    async def list_available_providers(
        self,
        org_id: UUID,
    ) -> List[str]:
        """
        List providers available for an organization.
        """
        from app.services.organization_service import OrganizationService
        
        org_service = OrganizationService(self.session)
        providers = await org_service.get_providers_for_organization(org_id)
        
        return [p.provider_type.value for p in providers]


# Dependency for FastAPI
async def get_metrics_service(session: AsyncSession) -> MetricsService:
    """Dependency to get metrics service instance."""
    return MetricsService(session)
