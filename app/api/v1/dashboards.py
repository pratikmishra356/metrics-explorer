"""Dashboard exploration API endpoints."""

from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_query_service_dep,
    validate_organization,
    get_db,
)
from app.models.dashboard import Dashboard, DashboardList
from app.models.organization import ProviderType
from app.models.query import DashboardQueryRequest, DashboardQueryResponse
from app.services.query_service import QueryService, QueryServiceError
from app.services.dashboard_sync_service import DashboardSyncService
from app.services.metric_extract_service import MetricExtractService
from app.services.metric_query_execution_service import (
    MetricQueryExecutionService,
    QueryExecutionError,
)
from app.db.repositories import DashboardRepository, MetricRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=DashboardList,
    summary="List dashboards",
    description="List all dashboards across configured providers for the organization.",
)
async def list_dashboards(
    org_id: UUID = Depends(validate_organization),
    query_service: QueryService = Depends(get_query_service_dep),
    tags: Optional[List[str]] = Query(
        None, description="Filter by tags"
    ),
    folder: Optional[str] = Query(
        None, description="Filter by folder name"
    ),
    provider: Optional[ProviderType] = Query(
        None, description="Filter by specific provider"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> DashboardList:
    """
    List dashboards from all configured providers.
    
    Returns a unified list of dashboards following OTel conventions,
    aggregated from Datadog, Prometheus, and Grafana based on the
    organization's configuration.
    """
    try:
        return await query_service.list_dashboards(
            org_id=org_id,
            tags=tags,
            folder=folder,
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


@router.post(
    "/sync",
    summary="Sync dashboards",
    description="Fetch dashboards from configured providers and store them in the database.",
)
async def sync_dashboards(
    org_id: UUID = Depends(validate_organization),
    db: AsyncSession = Depends(get_db),
    provider: Optional[ProviderType] = Query(
        None, description="Optional filter by specific provider"
    ),
) -> dict:
    """
    Sync dashboards from providers to database.
    
    Fetches dashboards from all configured providers (or a specific provider)
    and stores them in the database. If a dashboard with the same ID and
    provider already exists, it will be updated instead of creating a duplicate.
    """
    try:
        sync_service = DashboardSyncService(db)
        result = await sync_service.sync_dashboards(
            org_id=org_id,
            provider_type=provider,
        )
        return {
            "status": "success",
            "message": "Dashboards synced successfully",
            **result,
        }
    except Exception as e:
        logger.error("Failed to sync dashboards", error=str(e), org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "sync_failed",
                "message": str(e),
            },
        )


@router.get(
    "/stored",
    summary="List stored dashboards",
    description="List dashboards stored in the database for this organization.",
)
async def list_stored_dashboards(
    org_id: UUID = Depends(validate_organization),
    db: AsyncSession = Depends(get_db),
    provider: Optional[ProviderType] = Query(
        None, description="Filter by specific provider"
    ),
    limit: int = Query(2000, ge=1, le=5000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict:
    """
    List dashboards stored in the database.
    
    Returns dashboards that have been synced from providers and stored
    in the database for this organization.
    """
    try:
        dashboard_repo = DashboardRepository(db)
        dashboards = await dashboard_repo.list_for_org(
            org_id=org_id,
            provider_type=provider,
            limit=limit,
            offset=offset,
        )

        # Serialize dashboards
        dashboard_items = [
            {
                "id": d.id,
                "dashboard_id": d.dashboard_id,
                "title": d.title,
                "description": d.description,
                "provider_type": d.provider_type,
                "provider_source": d.provider_source,
                "metadata": d.metadata_ or {},
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in dashboards
        ]

        # Build per-provider breakdown
        providers_summary: dict = {}
        for d in dashboard_items:
            pt = d["provider_type"]
            if pt not in providers_summary:
                providers_summary[pt] = {"count": 0}
            providers_summary[pt]["count"] += 1

        return {
            "dashboards": dashboard_items,
            "total_count": len(dashboard_items),
            "providers_summary": providers_summary,
        }
    except Exception as e:
        logger.error("Failed to list stored dashboards", error=str(e), org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "query_error",
                "message": str(e),
            },
        )


# --- Parameterized routes below (must come after static routes) ---


@router.get(
    "/{dashboard_id}",
    response_model=Dashboard,
    summary="Get dashboard details",
    description="Get detailed information about a specific dashboard.",
)
async def get_dashboard(
    dashboard_id: str,
    org_id: UUID = Depends(validate_organization),
    query_service: QueryService = Depends(get_query_service_dep),
    provider: Optional[ProviderType] = Query(
        None, description="Specific provider to query (optional)"
    ),
) -> Dashboard:
    """
    Get detailed dashboard information.
    
    Returns the full dashboard with widgets, queries, and metadata
    in unified OTel format.
    
    If provider is not specified, queries all configured providers
    until the dashboard is found.
    """
    try:
        return await query_service.get_dashboard(
            org_id=org_id,
            dashboard_id=dashboard_id,
            provider_type=provider,
        )
    except QueryServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "dashboard_not_found",
                "message": str(e),
            },
        )


@router.post(
    "/{dashboard_id}/extract-metrics",
    summary="Extract metrics from dashboard",
    description="Fetch a dashboard's detail from the provider, extract all metric queries from its widgets, and store them in the database.",
)
async def extract_dashboard_metrics(
    dashboard_id: str,
    org_id: UUID = Depends(validate_organization),
    db: AsyncSession = Depends(get_db),
    provider: Optional[ProviderType] = Query(
        None, description="Specific provider to query (optional)"
    ),
) -> dict:
    """
    Extract metrics from a dashboard.
    
    Fetches the full dashboard detail from the provider, walks through
    all widgets (including nested group widgets), extracts individual
    metric queries, and stores them in the dashboard_metrics table.
    Metrics inside a group widget will include parent_group_details.
    """
    try:
        extract_service = MetricExtractService(db)
        result = await extract_service.extract_metrics(
            org_id=org_id,
            provider_dashboard_id=dashboard_id,
            provider_type=provider,
        )
        return {
            "status": "success",
            "message": "Metrics extracted successfully",
            **result,
        }
    except QueryServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "dashboard_not_found",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error(
            "Failed to extract metrics",
            error=str(e),
            dashboard_id=dashboard_id,
            org_id=str(org_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "extraction_failed",
                "message": str(e),
            },
        )


@router.post(
    "/{dashboard_id}/query",
    response_model=DashboardQueryResponse,
    summary="Query metrics for a dashboard",
    description=(
        "Execute one or more metric queries for a dashboard. "
        "Filters (template variable values) are optional — omit to query all values. "
        "The provider is resolved automatically from the stored dashboard."
    ),
)
async def query_dashboard_metrics(
    dashboard_id: str,
    request: DashboardQueryRequest = Body(...),
    org_id: UUID = Depends(validate_organization),
    db: AsyncSession = Depends(get_db),
    provider: Optional[ProviderType] = Query(
        None, description="Explicit provider type (auto-detected if omitted)"
    ),
) -> DashboardQueryResponse:
    """
    Execute metric queries against the provider backend.

    The request body contains a list of metric queries, each with optional
    tag/variable filters and a shared time range.  The system looks up
    the dashboard's provider from the database and routes the queries to
    the correct adapter (Datadog, Prometheus, Grafana).

    Example request body::

        {
          "queries": [
            {
              "metric_name": "aws.dynamodb.consumed_read_capacity_units",
              "aggregation": "avg",
              "filters": {"tablename": "my-table", "toast_environment": "prod"},
              "group_by": ["tablename"]
            }
          ],
          "time_range": {"relative": "1h"}
        }
    """
    try:
        svc = MetricQueryExecutionService(db)
        return await svc.execute(
            org_id=org_id,
            dashboard_id=dashboard_id,
            request=request,
            provider_type=provider,
        )
    except QueryExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "query_execution_failed",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error(
            "Failed to execute dashboard queries",
            error=str(e),
            dashboard_id=dashboard_id,
            org_id=str(org_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "query_error",
                "message": str(e),
            },
        )


@router.get(
    "/{dashboard_db_id}/metrics",
    summary="List extracted metrics for a dashboard",
    description="List all metrics that were extracted from a dashboard.",
)
async def list_dashboard_metrics(
    dashboard_db_id: str,
    org_id: UUID = Depends(validate_organization),
    db: AsyncSession = Depends(get_db),
    provider: Optional[str] = Query(
        None, description="Filter by provider"
    ),
    limit: int = Query(500, ge=1, le=5000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict:
    """
    List metrics extracted from a dashboard.
    
    Returns all metric rows stored in the dashboard_metrics table
    for a given dashboard (identified by its database ID).
    """
    try:
        metric_repo = MetricRepository(db)
        metrics = await metric_repo.list_for_dashboard(
            dashboard_id=dashboard_db_id,
            provider=provider,
            limit=limit,
            offset=offset,
        )

        metric_items = [
            {
                "id": m.id,
                "dashboard_id": m.dashboard_id,
                "provider": m.provider,
                "widget_id": m.widget_id,
                "name": m.name,
                "description": m.description,
                "details": m.details or {},
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in metrics
        ]

        # Per-provider breakdown
        providers_summary: dict = {}
        for m in metric_items:
            p = m["provider"]
            if p not in providers_summary:
                providers_summary[p] = {"count": 0}
            providers_summary[p]["count"] += 1

        return {
            "metrics": metric_items,
            "total_count": len(metric_items),
            "providers_summary": providers_summary,
        }
    except Exception as e:
        logger.error(
            "Failed to list dashboard metrics",
            error=str(e),
            dashboard_db_id=dashboard_db_id,
            org_id=str(org_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "query_error",
                "message": str(e),
            },
        )
