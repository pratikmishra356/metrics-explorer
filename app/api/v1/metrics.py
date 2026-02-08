"""Metrics query API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_metrics_service_dep,
    validate_organization,
)
from app.models.metrics import (
    MetricMetadataList,
    MetricQuery,
    MetricQueryResult,
)
from app.models.organization import ProviderType
from app.services.metrics_service import MetricsService
from app.services.query_service import QueryServiceError

logger = structlog.get_logger(__name__)

router = APIRouter()


class MetricQueryRequest(BaseModel):
    """Request model for metrics query."""

    metric_names: Optional[List[str]] = Field(
        None, description="Specific metric names to query"
    )
    metric_name_pattern: Optional[str] = Field(
        None, description="Regex pattern for metric names"
    )
    start_time: datetime = Field(
        ..., description="Query start time (ISO 8601)"
    )
    end_time: datetime = Field(
        ..., description="Query end time (ISO 8601)"
    )
    attribute_filters: dict = Field(
        default_factory=dict,
        description="Filter by attribute key-value pairs",
    )
    resource_filters: dict = Field(
        default_factory=dict,
        description="Filter by resource attributes",
    )
    aggregation: Optional[str] = Field(
        None,
        description="Aggregation function (avg, sum, min, max, count)",
    )
    group_by: List[str] = Field(
        default_factory=list,
        description="Attributes to group by",
    )
    step_seconds: Optional[int] = Field(
        60, ge=1, description="Step interval in seconds"
    )
    limit: int = Field(
        1000, ge=1, le=10000, description="Maximum data points"
    )

    def to_metric_query(self) -> MetricQuery:
        """Convert to MetricQuery model."""
        return MetricQuery(
            metric_names=self.metric_names,
            metric_name_pattern=self.metric_name_pattern,
            start_time=self.start_time,
            end_time=self.end_time,
            attribute_filters=self.attribute_filters,
            resource_filters=self.resource_filters,
            aggregation=self.aggregation,
            group_by=self.group_by,
            step_seconds=self.step_seconds,
            limit=self.limit,
        )


@router.post(
    "/query",
    response_model=MetricQueryResult,
    summary="Query metrics",
    description="Query metrics from configured providers using OTel-formatted query.",
)
async def query_metrics(
    query_request: MetricQueryRequest,
    org_id: UUID = Depends(validate_organization),
    metrics_service: MetricsService = Depends(get_metrics_service_dep),
    provider: Optional[ProviderType] = Query(
        None, description="Filter by specific provider"
    ),
) -> MetricQueryResult:
    """
    Query metrics from all configured providers.
    
    Accepts a query in universal format and translates it to
    provider-specific queries (Datadog, Prometheus, etc.).
    
    Returns metrics data in OTel MetricDataPoint format with
    unified attribute naming.
    """
    try:
        query = query_request.to_metric_query()
        return await metrics_service.query_metrics(
            org_id=org_id,
            query=query,
            provider_type=provider,
        )
    except QueryServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "query_error",
                "message": str(e),
            },
        )


@router.get(
    "/metadata",
    response_model=MetricMetadataList,
    summary="Get metrics metadata",
    description="Get metadata for available metrics.",
)
async def get_metrics_metadata(
    org_id: UUID = Depends(validate_organization),
    metrics_service: MetricsService = Depends(get_metrics_service_dep),
    metric_names: Optional[List[str]] = Query(
        None, description="Specific metric names to get metadata for"
    ),
    provider: Optional[ProviderType] = Query(
        None, description="Filter by specific provider"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
) -> MetricMetadataList:
    """
    Get metadata for available metrics.
    
    Returns information about metrics including name, description,
    unit, type, and available attributes.
    """
    try:
        return await metrics_service.get_metric_metadata(
            org_id=org_id,
            metric_names=metric_names,
            provider_type=provider,
            limit=limit,
        )
    except QueryServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "query_error",
                "message": str(e),
            },
        )


@router.get(
    "/providers",
    summary="List available providers",
    description="List metrics providers configured for the organization.",
)
async def list_providers(
    org_id: UUID = Depends(validate_organization),
    metrics_service: MetricsService = Depends(get_metrics_service_dep),
) -> dict:
    """
    List providers available for the organization.
    
    Returns the list of configured and active metrics providers.
    """
    try:
        providers = await metrics_service.list_available_providers(org_id)
        return {
            "providers": providers,
            "count": len(providers),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "query_error",
                "message": str(e),
            },
        )
