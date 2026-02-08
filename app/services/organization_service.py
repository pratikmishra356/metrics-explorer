"""Organization service for managing organization and provider configurations."""

import structlog
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrganizationModel, OrganizationProviderModel
from app.db.repositories import OrganizationRepository, OrganizationProviderRepository
from app.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationProvider,
    ProviderConfig,
    ProviderCreate,
    ProviderType,
)
from app.utils.encryption import decrypt_credentials, encrypt_credentials

logger = structlog.get_logger(__name__)


class OrganizationNotFoundError(Exception):
    """Raised when an organization is not found."""

    def __init__(self, org_id: str):
        self.org_id = org_id
        super().__init__(f"Organization not found: {org_id}")


class ProviderNotFoundError(Exception):
    """Raised when a provider is not found."""

    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        super().__init__(f"Provider not found: {provider_id}")


class OrganizationService:
    """Service for organization and provider operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.provider_repo = OrganizationProviderRepository(session)

    async def get_organization(self, org_id: UUID) -> Organization:
        """
        Get an organization by ID with its providers.
        
        Args:
            org_id: Organization UUID
            
        Returns:
            Organization with providers
            
        Raises:
            OrganizationNotFoundError: If organization not found
        """
        org_model = await self.org_repo.get_by_id(org_id)
        if not org_model:
            raise OrganizationNotFoundError(str(org_id))
        
        return self._model_to_organization(org_model)

    async def get_organization_by_slug(self, slug: str) -> Organization:
        """
        Get an organization by slug with its providers.
        
        Args:
            slug: Organization slug
            
        Returns:
            Organization with providers
            
        Raises:
            OrganizationNotFoundError: If organization not found
        """
        org_model = await self.org_repo.get_by_slug(slug)
        if not org_model:
            raise OrganizationNotFoundError(slug)
        
        return self._model_to_organization(org_model)

    async def get_providers_for_organization(
        self,
        org_id: UUID,
        provider_type: Optional[ProviderType] = None,
    ) -> List[OrganizationProvider]:
        """
        Get all active providers for an organization.
        
        Args:
            org_id: Organization UUID
            provider_type: Optional filter by provider type
            
        Returns:
            List of organization providers
        """
        provider_models = await self.provider_repo.get_providers_for_org(
            org_id, provider_type
        )
        return [self._model_to_provider(p) for p in provider_models]

    async def get_provider_credentials(
        self,
        org_id: UUID,
        provider_type: ProviderType,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get decrypted credentials for a specific provider.
        
        Args:
            org_id: Organization UUID
            provider_type: Type of provider
            provider_name: Optional specific provider name
            
        Returns:
            Decrypted credentials dictionary
            
        Raises:
            ProviderNotFoundError: If provider not found
        """
        provider = await self.provider_repo.get_provider_by_type(
            org_id, provider_type, provider_name
        )
        if not provider:
            raise ProviderNotFoundError(
                f"{provider_type.value}:{provider_name or 'default'}"
            )
        
        try:
            return decrypt_credentials(provider.encrypted_credentials)
        except Exception as e:
            logger.error(
                "Failed to decrypt credentials",
                org_id=str(org_id),
                provider_type=provider_type.value,
                error=str(e),
            )
            raise ValueError("Failed to decrypt provider credentials") from e

    async def get_provider_with_credentials(
        self,
        org_id: UUID,
        provider_type: ProviderType,
        provider_name: Optional[str] = None,
    ) -> tuple[OrganizationProvider, Dict[str, Any]]:
        """
        Get provider config with decrypted credentials.
        
        Returns:
            Tuple of (provider config, credentials dict)
        """
        provider = await self.provider_repo.get_provider_by_type(
            org_id, provider_type, provider_name
        )
        if not provider:
            raise ProviderNotFoundError(
                f"{provider_type.value}:{provider_name or 'default'}"
            )
        
        credentials = decrypt_credentials(provider.encrypted_credentials)
        return self._model_to_provider(provider), credentials

    async def create_organization(
        self, org_data: OrganizationCreate
    ) -> Organization:
        """Create a new organization."""
        from datetime import datetime
        
        org_model = OrganizationModel(
            name=org_data.name,
            slug=org_data.slug,
            description=org_data.description,
            metadata_=org_data.metadata,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        created = await self.org_repo.create(org_model)
        logger.info("Organization created", org_id=str(created.id), name=created.name)
        
        return self._model_to_organization(created)

    async def add_provider_to_organization(
        self,
        org_id: UUID,
        provider_data: ProviderCreate,
    ) -> OrganizationProvider:
        """Add a provider configuration to an organization."""
        from datetime import datetime
        
        # Verify organization exists
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise OrganizationNotFoundError(str(org_id))
        
        # Encrypt credentials
        encrypted = encrypt_credentials(provider_data.credentials)
        
        # Create provider model
        provider_model = OrganizationProviderModel(
            organization_id=str(org_id),
            provider_type=provider_data.provider_type.value,
            name=provider_data.name,
            description=provider_data.description,
            encrypted_credentials=encrypted,
            config=provider_data.config.model_dump() if provider_data.config else {},
            endpoint_url=provider_data.endpoint_url,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        created = await self.provider_repo.create(provider_model)
        logger.info(
            "Provider added to organization",
            org_id=str(org_id),
            provider_id=str(created.id),
            provider_type=provider_data.provider_type.value,
        )
        
        return self._model_to_provider(created)

    async def update_provider_credentials(
        self,
        provider_id: UUID,
        credentials: Dict[str, Any],
    ) -> OrganizationProvider:
        """Update credentials for a provider."""
        from datetime import datetime
        
        provider = await self.provider_repo.get_by_id(provider_id)
        if not provider:
            raise ProviderNotFoundError(str(provider_id))
        
        provider.encrypted_credentials = encrypt_credentials(credentials)
        provider.updated_at = datetime.utcnow()
        
        updated = await self.provider_repo.update(provider)
        logger.info("Provider credentials updated", provider_id=str(provider_id))
        
        return self._model_to_provider(updated)

    async def delete_provider(self, provider_id: UUID) -> bool:
        """Soft delete a provider configuration."""
        success = await self.provider_repo.delete(provider_id)
        if success:
            logger.info("Provider deleted", provider_id=str(provider_id))
        return success

    def _model_to_organization(self, model: OrganizationModel) -> Organization:
        """Convert database model to Organization pydantic model."""
        providers = [
            self._model_to_provider(p)
            for p in (model.providers or [])
            if p.is_active
        ]
        
        return Organization(
            id=model.id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            metadata=model.metadata_ or {},
            used_dashboards=model.used_dashboards or [],
            providers=providers,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _model_to_provider(
        self, model: OrganizationProviderModel
    ) -> OrganizationProvider:
        """Convert database model to OrganizationProvider pydantic model."""
        config = ProviderConfig(**(model.config or {}))
        
        # Convert string provider_type back to enum
        provider_type = ProviderType(model.provider_type) if isinstance(model.provider_type, str) else model.provider_type
        
        return OrganizationProvider(
            id=model.id,
            organization_id=model.organization_id,
            provider_type=provider_type,
            name=model.name,
            description=model.description,
            endpoint_url=model.endpoint_url,
            config=config,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


# Dependency for FastAPI
async def get_organization_service(
    session: AsyncSession,
) -> OrganizationService:
    """Dependency to get organization service instance."""
    return OrganizationService(session)
