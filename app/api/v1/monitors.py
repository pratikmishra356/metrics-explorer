"""Monitor exploration API endpoints."""

from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_query_service_dep,
    validate_organization,
)
from app.models.monitor import Monitor, MonitorList, MonitorStatus
from app.models.organization import ProviderType
from app.services.query_service import QueryService, QueryServiceError

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=MonitorList,
    summary="List monitors",
    description="List all monitors/alerts across configured providers for the organization.",
)
async def list_monitors(
    org_id: UUID = Depends(validate_organization),
    query_service: QueryService = Depends(get_query_service_dep),
    tags: Optional[List[str]] = Query(
        None, description="Filter by tags"
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status (ok, warning, alert, no_data, muted)",
    ),
    provider: Optional[ProviderType] = Query(
        None, description="Filter by specific provider"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> MonitorList:
    """
    List monitors from all configured providers.
    
    Returns a unified list of monitors following OTel conventions,
    including Datadog monitors, Prometheus alerting rules, and
    Grafana alert rules.
    
    The response includes status counts for quick overview.
    """
    try:
        return await query_service.list_monitors(
            org_id=org_id,
            tags=tags,
            status=status,
            provider_type=provider,
            limit=limit,
            offset=offset,
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
    "/{monitor_id}",
    response_model=Monitor,
    summary="Get monitor details",
    description="Get detailed information about a specific monitor.",
)
async def get_monitor(
    monitor_id: str,
    org_id: UUID = Depends(validate_organization),
    query_service: QueryService = Depends(get_query_service_dep),
    provider: Optional[ProviderType] = Query(
        None, description="Specific provider to query (optional)"
    ),
) -> Monitor:
    """
    Get detailed monitor information.
    
    Returns the full monitor with queries, thresholds, status,
    and metadata in unified OTel format.
    
    If provider is not specified, queries all configured providers
    until the monitor is found.
    """
    try:
        return await query_service.get_monitor(
            org_id=org_id,
            monitor_id=monitor_id,
            provider_type=provider,
        )
    except QueryServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "monitor_not_found",
                "message": str(e),
            },
        )
