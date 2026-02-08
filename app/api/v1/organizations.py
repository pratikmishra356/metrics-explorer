"""Organization management API endpoints."""

from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_organization_service_dep
from app.db.database import get_db
from app.db.repositories import (
    DashboardRepository,
    OrganizationRepository,
    TemplateVariableRepository,
)
from app.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationProvider,
    ProviderCreate,
    ProviderResponse,
    ProviderType,
)
from app.services.organization_service import (
    OrganizationNotFoundError,
    OrganizationService,
    ProviderNotFoundError,
)
logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=List[Organization],
    summary="List organizations",
    description="List all active organizations.",
)
async def list_organizations(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of organizations to return"),
    offset: int = Query(0, ge=0, description="Number of organizations to skip"),
    db: AsyncSession = Depends(get_db),
) -> List[Organization]:
    """List all active organizations."""
    try:
        org_repo = OrganizationRepository(db)
        org_models = await org_repo.list_all(limit=limit, offset=offset)
        
        # Convert to Pydantic models with providers loaded
        org_service = OrganizationService(db)
        organizations = []
        for org_model in org_models:
            # Use the service's internal method to convert properly
            org = org_service._model_to_organization(org_model)
            organizations.append(org)
        
        return organizations
    except Exception as e:
        logger.error("Failed to list organizations", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "list_failed",
                "message": str(e),
            },
        )


@router.post(
    "",
    response_model=Organization,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
    description="Create a new organization for provider configuration.",
)
async def create_organization(
    org_data: OrganizationCreate,
    org_service: OrganizationService = Depends(get_organization_service_dep),
) -> Organization:
    """Create a new organization."""
    try:
        return await org_service.create_organization(org_data)
    except Exception as e:
        logger.error("Failed to create organization", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "creation_failed",
                "message": str(e),
            },
        )


@router.get(
    "/{org_id}",
    response_model=Organization,
    summary="Get organization",
    description="Get organization details with provider configurations.",
)
async def get_organization(
    org_id: UUID,
    org_service: OrganizationService = Depends(get_organization_service_dep),
) -> Organization:
    """Get organization by ID."""
    try:
        return await org_service.get_organization(org_id)
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Organization not found: {org_id}",
            },
        )


@router.get(
    "/{org_id}/providers",
    response_model=List[ProviderResponse],
    summary="List organization providers",
    description="List all provider configurations for an organization.",
)
async def list_organization_providers(
    org_id: UUID,
    org_service: OrganizationService = Depends(get_organization_service_dep),
) -> List[ProviderResponse]:
    """List providers for an organization."""
    try:
        providers = await org_service.get_providers_for_organization(org_id)
        return [
            ProviderResponse(
                id=p.id,
                provider_type=p.provider_type,
                name=p.name,
                description=p.description,
                endpoint_url=p.endpoint_url,
                config=p.config,
                is_active=p.is_active,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in providers
        ]
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Organization not found: {org_id}",
            },
        )


@router.post(
    "/{org_id}/providers",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add provider to organization",
    description="Add a new provider configuration to an organization.",
)
async def add_provider_to_organization(
    org_id: UUID,
    provider_data: ProviderCreate,
    org_service: OrganizationService = Depends(get_organization_service_dep),
) -> ProviderResponse:
    """Add a provider to an organization."""
    try:
        provider = await org_service.add_provider_to_organization(
            org_id, provider_data
        )
        return ProviderResponse(
            id=provider.id,
            provider_type=provider.provider_type,
            name=provider.name,
            description=provider.description,
            endpoint_url=provider.endpoint_url,
            config=provider.config,
            is_active=provider.is_active,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Organization not found: {org_id}",
            },
        )
    except Exception as e:
        logger.error("Failed to add provider", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "creation_failed",
                "message": str(e),
            },
        )


@router.delete(
    "/{org_id}/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove provider from organization",
    description="Remove a provider configuration from an organization.",
)
async def remove_provider_from_organization(
    org_id: UUID,
    provider_id: UUID,
    org_service: OrganizationService = Depends(get_organization_service_dep),
):
    """Remove a provider from an organization."""
    try:
        # Verify org exists
        await org_service.get_organization(org_id)
        
        success = await org_service.delete_provider(provider_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "message": f"Provider not found: {provider_id}",
                },
            )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Organization not found: {org_id}",
            },
        )


@router.get(
    "/{org_id}/template-variables",
    summary="List template variables",
    description=(
        "List resolved template variables stored in the database for an organization. "
        "Optionally filter by dashboard_id or provider. No live provider API calls are made."
    ),
)
async def list_template_variables(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    dashboard_id: Optional[str] = Query(None, description="Filter by dashboard DB id"),
    provider: Optional[str] = Query(None, description="Filter by provider (e.g. datadog)"),
) -> dict:
    """List stored template variables for an organization."""
    try:
        repo = TemplateVariableRepository(db)
        variables = await repo.list_for_org(
            org_id=org_id,
            provider=provider,
            dashboard_id=dashboard_id,
        )
        return {
            "template_variables": [
                {
                    "id": v.id,
                    "organization_id": v.organization_id,
                    "dashboard_id": v.dashboard_id,
                    "variable_name": v.variable_name,
                    "tag_key": v.tag_key,
                    "default_value": v.default_value,
                    "values": v.values or [],
                    "provider": v.provider,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "updated_at": v.updated_at.isoformat() if v.updated_at else None,
                }
                for v in variables
            ],
            "total_count": len(variables),
        }
    except Exception as e:
        logger.error("Failed to list template variables", error=str(e), org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "query_error", "message": str(e)},
        )


# ==================== Used Dashboards ====================


class UsedDashboardsUpdate(BaseModel):
    """Request to set the list of important dashboard IDs."""
    dashboard_ids: List[str] = Field(
        ..., description="List of provider dashboard IDs to mark as important"
    )


@router.get(
    "/{org_id}/used-dashboards",
    summary="Get used dashboards",
    description=(
        "Get the list of important dashboards for this organisation, "
        "including their stored metadata."
    ),
)
async def get_used_dashboards(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service_dep),
) -> dict:
    """Return the used_dashboards list with full dashboard details."""
    try:
        org = await org_service.get_organization(org_id)
        ids = org.used_dashboards or []
        if not ids:
            return {"used_dashboards": [], "dashboard_ids": [], "total_count": 0}

        dash_repo = DashboardRepository(db)
        dashboards = await dash_repo.get_by_dashboard_ids(org_id, ids)

        return {
            "dashboard_ids": ids,
            "used_dashboards": [
                {
                    "id": d.id,
                    "dashboard_id": d.dashboard_id,
                    "title": d.title,
                    "description": d.description,
                    "provider_type": d.provider_type,
                }
                for d in dashboards
            ],
            "total_count": len(dashboards),
        }
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Organization not found: {org_id}"},
        )


@router.put(
    "/{org_id}/used-dashboards",
    summary="Set used dashboards",
    description="Replace the list of important dashboard IDs for this organisation.",
)
async def set_used_dashboards(
    org_id: UUID,
    body: UsedDashboardsUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set the used_dashboards list."""
    try:
        org_repo = OrganizationRepository(db)
        org = await org_repo.get_by_id(org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": f"Organization not found: {org_id}"},
            )
        org.used_dashboards = body.dashboard_ids
        from datetime import datetime
        org.updated_at = datetime.utcnow()
        await db.commit()
        return {
            "status": "success",
            "used_dashboards": body.dashboard_ids,
            "total_count": len(body.dashboard_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update used dashboards", error=str(e), org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "update_failed", "message": str(e)},
        )


# ==================== Search ====================


@router.get(
    "/{org_id}/dashboards/search",
    summary="Search dashboards",
    description=(
        "List or search stored dashboards by title or ID. "
        "If search is provided, filters results. Space-separated terms are OR'd. Use * as wildcard."
    ),
)
async def search_dashboards(
    org_id: UUID,
    search: Optional[str] = Query(None, description="Optional search term (supports * wildcard). If omitted, returns all dashboards."),
    provider: Optional[ProviderType] = Query(None, description="Filter by provider"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List or search dashboards by title or ID with wildcard support."""
    try:
        dash_repo = DashboardRepository(db)
        results = await dash_repo.search(
            org_id=org_id,
            search=search or "",
            provider_type=provider,
            limit=limit,
            offset=offset,
        )
        return {
            "dashboards": [
                {
                    "id": d.id,
                    "dashboard_id": d.dashboard_id,
                    "title": d.title,
                    "description": d.description,
                    "provider_type": d.provider_type,
                    "provider_source": d.provider_source,
                }
                for d in results
            ],
            "total_count": len(results),
            "search": search,
        }
    except Exception as e:
        logger.error("Dashboard search failed", error=str(e), org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "search_failed", "message": str(e)},
        )


@router.get(
    "/{org_id}/dashboards/{dashboard_db_id}/metrics/search",
    summary="Search metrics in a dashboard",
    description=(
        "List or search extracted metrics within a dashboard by name. "
        "If search is provided, filters results. Space-separated terms are OR'd. Use * as wildcard."
    ),
)
async def search_dashboard_metrics(
    org_id: UUID,
    dashboard_db_id: str,
    search: Optional[str] = Query(None, description="Optional search term (supports * wildcard). If omitted, returns all metrics."),
    provider: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List or search metrics within a dashboard."""
    from app.db.repositories import MetricRepository

    try:
        metric_repo = MetricRepository(db)
        results = await metric_repo.search(
            dashboard_id=dashboard_db_id,
            search=search or "",
            provider=provider,
            limit=limit,
            offset=offset,
        )
        return {
            "metrics": [
                {
                    "id": m.id,
                    "widget_id": m.widget_id,
                    "name": m.name,
                    "description": m.description,
                    "provider": m.provider,
                    "details": m.details or {},
                }
                for m in results
            ],
            "total_count": len(results),
            "search": search,
        }
    except Exception as e:
        logger.error("Metric search failed", error=str(e), dashboard_db_id=dashboard_db_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "search_failed", "message": str(e)},
        )


@router.get(
    "/{org_id}/dashboards/{dashboard_db_id}/variables/{variable_name}/values",
    summary="Get values for a template variable",
    description=(
        "Get the resolved values for a specific template variable in a dashboard. "
        "Supports optional search/filter on the values list."
    ),
)
async def get_variable_values(
    org_id: UUID,
    dashboard_db_id: str,
    variable_name: str,
    search: Optional[str] = Query(None, description="Filter values (case-insensitive contains)"),
    limit: int = Query(200, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get resolved values for a template variable."""
    try:
        tv_repo = TemplateVariableRepository(db)
        variables = await tv_repo.list_for_dashboard(dashboard_db_id)

        match = next((v for v in variables if v.variable_name == variable_name), None)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "message": f"Variable '{variable_name}' not found in dashboard {dashboard_db_id}",
                },
            )

        values = match.values or []
        if search:
            q = search.lower()
            values = [v for v in values if q in v.lower()]

        total = len(values)
        values = values[:limit]

        return {
            "variable_name": match.variable_name,
            "tag_key": match.tag_key,
            "default_value": match.default_value,
            "values": values,
            "total_count": total,
            "returned_count": len(values),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get variable values", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "query_error", "message": str(e)},
        )
