"""Organization and provider configuration models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """Supported metrics provider types."""

    DATADOG = "datadog"
    PROMETHEUS = "prometheus"
    GRAFANA = "grafana"


class ProviderCredentials(BaseModel):
    """Base model for provider credentials (stored encrypted)."""

    pass


class DatadogCredentials(ProviderCredentials):
    """Datadog API credentials."""

    api_key: str = Field(..., description="Datadog API key")
    app_key: str = Field(..., description="Datadog Application key")
    site: str = Field(
        default="datadoghq.com",
        description="Datadog site (e.g., datadoghq.com, datadoghq.eu)",
    )


class PrometheusCredentials(ProviderCredentials):
    """Prometheus connection credentials."""

    # Prometheus typically uses basic auth or bearer token
    username: Optional[str] = Field(None, description="Basic auth username")
    password: Optional[str] = Field(None, description="Basic auth password")
    bearer_token: Optional[str] = Field(None, description="Bearer token for auth")


class GrafanaCredentials(ProviderCredentials):
    """Grafana API credentials."""

    api_key: str = Field(..., description="Grafana API key or service account token")


class ProviderConfig(BaseModel):
    """Non-sensitive provider configuration."""

    # Query settings
    timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    # Rate limiting
    rate_limit_requests: int = Field(
        default=100, description="Max requests per minute"
    )
    
    # Provider-specific settings
    custom_settings: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific custom settings"
    )


class OrganizationProvider(BaseModel):
    """Provider configuration for an organization."""

    id: UUID
    organization_id: UUID
    provider_type: ProviderType
    name: str = Field(..., description="Display name for this provider instance")
    description: Optional[str] = None
    endpoint_url: Optional[str] = Field(
        None, description="Provider endpoint URL (for Prometheus/Grafana)"
    )
    config: ProviderConfig = Field(default_factory=ProviderConfig)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Organization(BaseModel):
    """Organization model with provider configurations."""

    id: UUID
    name: str
    slug: str = Field(..., description="URL-friendly organization identifier")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    used_dashboards: List[str] = Field(
        default_factory=list,
        description="Provider dashboard IDs marked as important",
    )
    providers: List[OrganizationProvider] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Request/Response models for API
class OrganizationCreate(BaseModel):
    """Request model for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProviderCreate(BaseModel):
    """Request model for adding a provider to an organization."""

    provider_type: ProviderType
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    credentials: Dict[str, Any] = Field(
        ..., description="Provider-specific credentials"
    )
    config: Optional[ProviderConfig] = None


class ProviderResponse(BaseModel):
    """Response model for provider (without credentials)."""

    id: UUID
    provider_type: ProviderType
    name: str
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    config: ProviderConfig
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
