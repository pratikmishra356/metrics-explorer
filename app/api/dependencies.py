"""API dependencies for request handling."""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.organization_service import (
    OrganizationNotFoundError,
    OrganizationService,
)
from app.services.query_service import QueryService
from app.services.metrics_service import MetricsService

logger = structlog.get_logger(__name__)


async def get_organization_id(
    x_organization_id: str = Header(
        ...,
        description="Organization ID for provider routing",
        alias="X-Organization-Id",
    ),
) -> UUID:
    """
    Extract and validate organization ID from request header.
    
    The X-Organization-Id header is required for all API endpoints
    to determine which provider(s) to query.
    """
    try:
        return UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_organization_id",
                "message": "X-Organization-Id must be a valid UUID",
            },
        )


async def validate_organization(
    org_id: UUID = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Validate that organization exists and is active.
    """
    try:
        org_service = OrganizationService(db)
        await org_service.get_organization(org_id)
        return org_id
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "organization_not_found",
                "message": f"Organization not found: {org_id}",
            },
        )


async def get_query_service_dep(
    db: AsyncSession = Depends(get_db),
) -> QueryService:
    """Dependency to get QueryService instance."""
    return QueryService(db)


async def get_metrics_service_dep(
    db: AsyncSession = Depends(get_db),
) -> MetricsService:
    """Dependency to get MetricsService instance."""
    return MetricsService(db)


async def get_organization_service_dep(
    db: AsyncSession = Depends(get_db),
) -> OrganizationService:
    """Dependency to get OrganizationService instance."""
    return OrganizationService(db)
