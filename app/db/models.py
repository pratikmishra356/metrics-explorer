"""SQLAlchemy ORM models for database tables."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.organization import ProviderType


def generate_uuid() -> str:
    """Generate UUID string for primary key."""
    return str(uuid.uuid4())


class OrganizationModel(Base):
    """Database model for organizations."""

    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)
    used_dashboards = Column(JSON, nullable=False, default=list)  # list of provider dashboard IDs
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    providers = relationship(
        "OrganizationProviderModel",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"


class OrganizationProviderModel(Base):
    """Database model for organization-provider mappings with encrypted credentials."""

    __tablename__ = "organization_providers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_type = Column(String(50), nullable=False)  # Store enum value as string
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Encrypted credentials stored as base64 string
    encrypted_credentials = Column(Text, nullable=False)

    # Provider-specific configuration (non-sensitive)
    config = Column(JSON, nullable=True, default=dict)

    # Provider endpoint URL
    endpoint_url = Column(String(1024), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    organization = relationship(
        "OrganizationModel",
        back_populates="providers",
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider_type",
            "name",
            name="uq_org_provider_name",
        ),
        Index("ix_org_provider_active", "organization_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationProvider(id={self.id}, "
            f"org_id={self.organization_id}, "
            f"type={self.provider_type})>"
        )


class OrganizationDashboardModel(Base):
    """Database model for organization dashboards."""

    __tablename__ = "organization_dashboards"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dashboard_id = Column(String(255), nullable=False)  # Provider's dashboard ID
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    provider_type = Column(String(50), nullable=False)  # Which provider this came from
    provider_source = Column(String(255), nullable=True)  # Provider-specific identifier
    
    # Additional metadata
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)
    
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    organization = relationship(
        "OrganizationModel",
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dashboard_id",
            "provider_type",
            name="uq_org_dashboard_provider",
        ),
        Index("ix_org_dashboard_active", "organization_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationDashboard(id={self.id}, "
            f"org_id={self.organization_id}, "
            f"dashboard_id={self.dashboard_id}, "
            f"title={self.title[:30]})>"
        )


class DashboardMetricModel(Base):
    """Database model for metrics extracted from dashboards (one row per widget).

    Generic across providers -- Datadog, Grafana, Prometheus, etc.
    Provider-specific widget details live in the `details` JSON column.
    """

    __tablename__ = "dashboard_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dashboard_id = Column(
        String(36),
        ForeignKey("organization_dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)  # e.g. "datadog", "grafana"
    widget_id = Column(String(255), nullable=True)  # Provider-specific widget ID
    name = Column(String(512), nullable=True)  # Human-readable metric / widget name
    description = Column(Text, nullable=True)  # Optional description or summary
    details = Column(JSON, nullable=False, default=dict)  # Full widget data (requests, queries, formulas, parent_group, etc.)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    dashboard = relationship("OrganizationDashboardModel")

    # Constraints and indexes
    __table_args__ = (
        Index("ix_dashboard_metric_provider", "dashboard_id", "provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<DashboardMetric(id={self.id}, "
            f"dashboard_id={self.dashboard_id}, "
            f"provider={self.provider}, "
            f"name={self.name})>"
        )


class TemplateVariableModel(Base):
    """Resolved template variables from dashboards.

    Unique per (organization, dashboard, variable_name).
    Values are resolved at metric-extraction time via the provider adapter
    (e.g. Datadog GET /api/v1/tags/hosts).
    """

    __tablename__ = "template_variables"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dashboard_id = Column(
        String(36),
        ForeignKey("organization_dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variable_name = Column(String(255), nullable=False)
    tag_key = Column(String(255), nullable=False)
    default_value = Column(String(255), nullable=True)
    values = Column(JSON, nullable=False, default=list)
    provider = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    organization = relationship("OrganizationModel")
    dashboard = relationship("OrganizationDashboardModel")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dashboard_id",
            "variable_name",
            name="uq_org_dash_varname",
        ),
        Index("ix_template_var_org_active", "organization_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<TemplateVariable(id={self.id}, "
            f"org_id={self.organization_id}, "
            f"dashboard_id={self.dashboard_id}, "
            f"var={self.variable_name})>"
        )
