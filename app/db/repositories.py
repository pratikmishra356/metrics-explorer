"""Data access layer for database operations."""

from typing import Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    OrganizationModel,
    OrganizationProviderModel,
    OrganizationDashboardModel,
    DashboardMetricModel,
    TemplateVariableModel,
)
from app.models.organization import ProviderType


class OrganizationRepository:
    """Repository for organization data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, org_id: Union[str, UUID]) -> Optional[OrganizationModel]:
        """Get organization by ID."""
        org_id_str = str(org_id)
        query = (
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.providers))
            .where(OrganizationModel.id == org_id_str)
            .where(OrganizationModel.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[OrganizationModel]:
        """Get organization by slug."""
        query = (
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.providers))
            .where(OrganizationModel.slug == slug)
            .where(OrganizationModel.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[OrganizationModel]:
        """List all active organizations with providers loaded."""
        query = (
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.providers))
            .where(OrganizationModel.is_active == True)
            .order_by(OrganizationModel.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, organization: OrganizationModel) -> OrganizationModel:
        """Create a new organization."""
        self.session.add(organization)
        await self.session.flush()
        await self.session.refresh(organization)
        return organization

    async def update(self, organization: OrganizationModel) -> OrganizationModel:
        """Update an organization."""
        await self.session.flush()
        await self.session.refresh(organization)
        return organization

    async def delete(self, org_id: Union[str, UUID]) -> bool:
        """Soft delete an organization."""
        org = await self.get_by_id(org_id)
        if org:
            org.is_active = False
            await self.session.flush()
            return True
        return False


class OrganizationProviderRepository:
    """Repository for organization provider data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, provider_id: Union[str, UUID]) -> Optional[OrganizationProviderModel]:
        """Get provider by ID."""
        provider_id_str = str(provider_id)
        query = (
            select(OrganizationProviderModel)
            .where(OrganizationProviderModel.id == provider_id_str)
            .where(OrganizationProviderModel.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_providers_for_org(
        self,
        org_id: Union[str, UUID],
        provider_type: Optional[ProviderType] = None,
    ) -> List[OrganizationProviderModel]:
        """Get all active providers for an organization."""
        query = (
            select(OrganizationProviderModel)
            .where(OrganizationProviderModel.organization_id == str(org_id))
            .where(OrganizationProviderModel.is_active == True)
        )
        if provider_type:
            query = query.where(
                OrganizationProviderModel.provider_type == provider_type.value
            )
        query = query.order_by(OrganizationProviderModel.name)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_provider_by_type(
        self,
        org_id: Union[str, UUID],
        provider_type: ProviderType,
        name: Optional[str] = None,
    ) -> Optional[OrganizationProviderModel]:
        """Get a specific provider for an organization by type and optionally name."""
        query = (
            select(OrganizationProviderModel)
            .where(OrganizationProviderModel.organization_id == str(org_id))
            .where(OrganizationProviderModel.provider_type == provider_type.value)
            .where(OrganizationProviderModel.is_active == True)
        )
        if name:
            query = query.where(OrganizationProviderModel.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self, provider: OrganizationProviderModel
    ) -> OrganizationProviderModel:
        """Create a new provider configuration."""
        self.session.add(provider)
        await self.session.flush()
        await self.session.refresh(provider)
        return provider

    async def update(
        self, provider: OrganizationProviderModel
    ) -> OrganizationProviderModel:
        """Update a provider configuration."""
        await self.session.flush()
        await self.session.refresh(provider)
        return provider

    async def delete(self, provider_id: Union[str, UUID]) -> bool:
        """Soft delete a provider configuration."""
        provider = await self.get_by_id(provider_id)
        if provider:
            provider.is_active = False
            await self.session.flush()
            return True
        return False


class DashboardRepository:
    """Repository for organization dashboard data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self, dashboard_db_id: Union[str, UUID]
    ) -> Optional[OrganizationDashboardModel]:
        """Get dashboard by database ID."""
        dashboard_id_str = str(dashboard_db_id)
        query = (
            select(OrganizationDashboardModel)
            .where(OrganizationDashboardModel.id == dashboard_id_str)
            .where(OrganizationDashboardModel.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_provider_id(
        self,
        org_id: Union[str, UUID],
        dashboard_id: str,
        provider_type: ProviderType,
    ) -> Optional[OrganizationDashboardModel]:
        """Get dashboard by provider dashboard ID and provider type."""
        query = (
            select(OrganizationDashboardModel)
            .where(OrganizationDashboardModel.organization_id == str(org_id))
            .where(OrganizationDashboardModel.dashboard_id == dashboard_id)
            .where(OrganizationDashboardModel.provider_type == provider_type.value)
            .where(OrganizationDashboardModel.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_org(
        self,
        org_id: Union[str, UUID],
        provider_type: Optional[ProviderType] = None,
        limit: int = 2000,
        offset: int = 0,
    ) -> List[OrganizationDashboardModel]:
        """List all dashboards for an organization."""
        query = (
            select(OrganizationDashboardModel)
            .where(OrganizationDashboardModel.organization_id == str(org_id))
            .where(OrganizationDashboardModel.is_active == True)
        )
        if provider_type:
            query = query.where(
                OrganizationDashboardModel.provider_type == provider_type.value
            )
        query = query.order_by(OrganizationDashboardModel.title).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_or_update(
        self,
        org_id: Union[str, UUID],
        dashboard_id: str,
        title: str,
        description: Optional[str],
        provider_type: ProviderType,
        provider_source: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> OrganizationDashboardModel:
        """Create or update a dashboard (upsert by org_id, dashboard_id, provider_type)."""
        from datetime import datetime

        existing = await self.get_by_provider_id(org_id, dashboard_id, provider_type)
        
        if existing:
            # Update existing
            existing.title = title
            existing.description = description
            existing.provider_source = provider_source
            if metadata:
                existing.metadata_ = metadata
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            # Create new
            dashboard = OrganizationDashboardModel(
                organization_id=str(org_id),
                dashboard_id=dashboard_id,
                title=title,
                description=description,
                provider_type=provider_type.value,
                provider_source=provider_source,
                metadata_=metadata or {},
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(dashboard)
            await self.session.flush()
            await self.session.refresh(dashboard)
            return dashboard

    async def search(
        self,
        org_id: Union[str, UUID],
        search: Optional[str] = None,
        provider_type: Optional[ProviderType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OrganizationDashboardModel]:
        """
        List or search dashboards by title or dashboard_id using SQL ILIKE.

        If search is None or empty, returns all dashboards.
        Space-separated terms are treated as OR.
        ``*`` is converted to ``%`` for SQL wildcard matching.
        """
        query = (
            select(OrganizationDashboardModel)
            .where(OrganizationDashboardModel.organization_id == str(org_id))
            .where(OrganizationDashboardModel.is_active == True)
        )
        if provider_type:
            query = query.where(
                OrganizationDashboardModel.provider_type == provider_type.value
            )

        if search:
            terms = [t.strip() for t in search.split() if t.strip()]
            if terms:
                conditions = []
                for term in terms:
                    pattern = f"%{term.replace('*', '%')}%"
                    conditions.append(OrganizationDashboardModel.title.ilike(pattern))
                    conditions.append(OrganizationDashboardModel.dashboard_id.ilike(pattern))
                query = query.where(or_(*conditions))

        query = query.order_by(OrganizationDashboardModel.title).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_dashboard_ids(
        self,
        org_id: Union[str, UUID],
        dashboard_ids: List[str],
    ) -> List[OrganizationDashboardModel]:
        """Get dashboards by a list of provider dashboard IDs."""
        if not dashboard_ids:
            return []
        query = (
            select(OrganizationDashboardModel)
            .where(OrganizationDashboardModel.organization_id == str(org_id))
            .where(OrganizationDashboardModel.dashboard_id.in_(dashboard_ids))
            .where(OrganizationDashboardModel.is_active == True)
            .order_by(OrganizationDashboardModel.title)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(self, dashboard_db_id: Union[str, UUID]) -> bool:
        """Soft delete a dashboard."""
        dashboard = await self.get_by_id(dashboard_db_id)
        if dashboard:
            dashboard.is_active = False
            await self.session.flush()
            return True
        return False


class MetricRepository:
    """Repository for dashboard metric data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self, metric_id: Union[str, UUID]
    ) -> Optional[DashboardMetricModel]:
        """Get metric by database ID."""
        metric_id_str = str(metric_id)
        query = (
            select(DashboardMetricModel)
            .where(DashboardMetricModel.id == metric_id_str)
            .where(DashboardMetricModel.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_dashboard(
        self,
        dashboard_id: Union[str, UUID],
        provider: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[DashboardMetricModel]:
        """List all metrics for a dashboard."""
        query = (
            select(DashboardMetricModel)
            .where(DashboardMetricModel.dashboard_id == str(dashboard_id))
            .where(DashboardMetricModel.is_active == True)
        )
        if provider:
            query = query.where(DashboardMetricModel.provider == provider)
        query = (
            query.order_by(DashboardMetricModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_or_update(
        self,
        dashboard_id: Union[str, UUID],
        provider: str,
        widget_id: Optional[str],
        name: Optional[str],
        description: Optional[str],
        details: Dict,
    ) -> DashboardMetricModel:
        """Create or update a metric (upsert by dashboard_id + provider + widget_id)."""
        from datetime import datetime

        dashboard_id_str = str(dashboard_id)

        # Try to find an existing metric with the same widget_id
        existing: Optional[DashboardMetricModel] = None
        if widget_id:
            stmt = (
                select(DashboardMetricModel)
                .where(DashboardMetricModel.dashboard_id == dashboard_id_str)
                .where(DashboardMetricModel.provider == provider)
                .where(DashboardMetricModel.widget_id == widget_id)
                .where(DashboardMetricModel.is_active == True)
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

        if existing:
            existing.name = name
            existing.description = description
            existing.details = details
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            metric = DashboardMetricModel(
                dashboard_id=dashboard_id_str,
                provider=provider,
                widget_id=widget_id,
                name=name,
                description=description,
                details=details,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(metric)
            await self.session.flush()
            await self.session.refresh(metric)
            return metric

    async def search(
        self,
        dashboard_id: Union[str, UUID],
        search: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DashboardMetricModel]:
        """
        List or search metrics within a dashboard by name or query strings using SQL ILIKE.

        If search is None or empty, returns all metrics.
        Searches both the ``name`` column and the ``details`` JSON (cast to text)
        so that metric names inside query strings are also matched.

        Space-separated terms are treated as OR.
        ``*`` is converted to ``%`` for SQL wildcard matching.
        """
        from sqlalchemy import cast, String as SAString

        query = (
            select(DashboardMetricModel)
            .where(DashboardMetricModel.dashboard_id == str(dashboard_id))
            .where(DashboardMetricModel.is_active == True)
        )
        if provider:
            query = query.where(DashboardMetricModel.provider == provider)

        if search:
            terms = [t.strip() for t in search.split() if t.strip()]
            if terms:
                conditions = []
                for term in terms:
                    pattern = f"%{term.replace('*', '%')}%"
                    conditions.append(DashboardMetricModel.name.ilike(pattern))
                    conditions.append(cast(DashboardMetricModel.details, SAString).ilike(pattern))
                query = query.where(or_(*conditions))

        query = query.order_by(DashboardMetricModel.name).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_for_dashboard(
        self, dashboard_id: Union[str, UUID]
    ) -> int:
        """Soft-delete all metrics for a dashboard. Returns count of deleted rows."""
        from datetime import datetime
        from sqlalchemy import update

        dashboard_id_str = str(dashboard_id)
        stmt = (
            update(DashboardMetricModel)
            .where(DashboardMetricModel.dashboard_id == dashboard_id_str)
            .where(DashboardMetricModel.is_active == True)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount


class TemplateVariableRepository:
    """Repository for template variable data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        org_id: Union[str, UUID],
        dashboard_id: Union[str, UUID],
        variable_name: str,
        tag_key: str,
        default_value: Optional[str],
        values: List,
        provider: str,
    ) -> TemplateVariableModel:
        """Insert or update a template variable (unique on org + dashboard + name)."""
        from datetime import datetime

        org_id_str = str(org_id)
        dashboard_id_str = str(dashboard_id)

        stmt = (
            select(TemplateVariableModel)
            .where(TemplateVariableModel.organization_id == org_id_str)
            .where(TemplateVariableModel.dashboard_id == dashboard_id_str)
            .where(TemplateVariableModel.variable_name == variable_name)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.tag_key = tag_key
            existing.default_value = default_value
            existing.values = values
            existing.provider = provider
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            tv = TemplateVariableModel(
                organization_id=org_id_str,
                dashboard_id=dashboard_id_str,
                variable_name=variable_name,
                tag_key=tag_key,
                default_value=default_value,
                values=values,
                provider=provider,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(tv)
            await self.session.flush()
            await self.session.refresh(tv)
            return tv

    async def list_for_dashboard(
        self,
        dashboard_id: Union[str, UUID],
    ) -> List[TemplateVariableModel]:
        """List all active template variables for a dashboard."""
        stmt = (
            select(TemplateVariableModel)
            .where(TemplateVariableModel.dashboard_id == str(dashboard_id))
            .where(TemplateVariableModel.is_active == True)
            .order_by(TemplateVariableModel.variable_name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_org(
        self,
        org_id: Union[str, UUID],
        provider: Optional[str] = None,
        dashboard_id: Optional[Union[str, UUID]] = None,
    ) -> List[TemplateVariableModel]:
        """List all active template variables for an organization."""
        stmt = (
            select(TemplateVariableModel)
            .where(TemplateVariableModel.organization_id == str(org_id))
            .where(TemplateVariableModel.is_active == True)
        )
        if provider:
            stmt = stmt.where(TemplateVariableModel.provider == provider)
        if dashboard_id:
            stmt = stmt.where(
                TemplateVariableModel.dashboard_id == str(dashboard_id)
            )
        stmt = stmt.order_by(TemplateVariableModel.variable_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
