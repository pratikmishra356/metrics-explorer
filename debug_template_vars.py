#!/usr/bin/env python3
"""Script to extract metrics and check template variable logs."""

import asyncio
import sys
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.db.repositories import DashboardRepository
from app.services.metric_extract_service import MetricExtractService

# Configure logging to see debug messages
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def find_dashboard(session: AsyncSession, org_id: UUID, search_term: str):
    """Find dashboard by title."""
    repo = DashboardRepository(session)
    dashboards = await repo.list_for_org(org_id, limit=1000)
    
    matching = [d for d in dashboards if search_term.lower() in d.title.lower()]
    return matching


async def extract_and_log(session: AsyncSession, org_id: UUID, dashboard_id: str):
    """Extract metrics and log template variable details."""
    logger.info("=" * 80)
    logger.info("STARTING METRIC EXTRACTION FOR DEBUGGING")
    logger.info("=" * 80)
    
    extract_service = MetricExtractService(session)
    
    try:
        result = await extract_service.extract_metrics(
            org_id=org_id,
            provider_dashboard_id=dashboard_id,
        )
        
        logger.info("=" * 80)
        logger.info("EXTRACTION COMPLETE")
        logger.info("=" * 80)
        logger.info("Result", **result)
        
        return result
    except Exception as e:
        logger.error("Extraction failed", error=str(e), error_type=type(e).__name__)
        import traceback
        logger.error("Traceback", traceback=traceback.format_exc())
        raise


async def main():
    if len(sys.argv) < 3:
        print("Usage: python debug_template_vars.py <org_id> <dashboard_search_term>")
        print("Example: python debug_template_vars.py 11278f66-513f-40e1-805d-6119c3abb404 'DynamoDB'")
        sys.exit(1)
    
    org_id_str = sys.argv[1]
    search_term = sys.argv[2]
    
    try:
        org_id = UUID(org_id_str)
    except ValueError:
        print(f"Invalid org_id: {org_id_str}")
        sys.exit(1)
    
    async with async_session_maker() as session:
        try:
            # Find dashboard
            logger.info("Searching for dashboard", search_term=search_term)
            dashboards = await find_dashboard(session, org_id, search_term)
            
            if not dashboards:
                logger.error("No dashboards found", search_term=search_term)
                return
            
            logger.info("Found dashboards", count=len(dashboards))
            for d in dashboards:
                logger.info(
                    "Dashboard",
                    id=d.id,
                    dashboard_id=d.dashboard_id,
                    title=d.title,
                    provider=d.provider_type,
                )
            
            # Use first matching dashboard
            dashboard = dashboards[0]
            logger.info("Using dashboard", dashboard_id=dashboard.dashboard_id, title=dashboard.title)
            
            # Extract metrics
            await extract_and_log(session, org_id, dashboard.dashboard_id)
            
            await session.commit()
            
        except Exception as e:
            logger.error("Error", error=str(e))
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
