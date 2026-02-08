"""Datadog API client for metrics exploration."""

from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class DatadogClient:
    """HTTP client for Datadog API."""

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
        timeout: int = 30,
    ):
        """
        Initialize Datadog client.
        
        Args:
            api_key: Datadog API key
            app_key: Datadog Application key
            site: Datadog site (datadoghq.com, datadoghq.eu, etc.)
                     If site already starts with 'api.', it will be used as-is
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        
        # Handle site URL - if it already includes 'api.', use it directly
        # Otherwise, prepend 'api.'
        if site.startswith("api."):
            self.base_url = f"https://{site}/api"
        else:
            self.base_url = f"https://api.{site}/api"
        
        self.timeout = timeout
        logger.info(
            "Initialized Datadog client",
            base_url=self.base_url,
            site=site,
            has_api_key=bool(api_key),
            has_app_key=bool(app_key),
        )
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "DD-API-KEY": api_key,
                "DD-APPLICATION-KEY": app_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ==================== Dashboard APIs ====================

    async def list_dashboards(self) -> Dict[str, Any]:
        """List all dashboards."""
        url = "/v1/dashboard"
        logger.debug("Calling Datadog API", url=url, base_url=self.base_url)
        try:
            response = await self._client.get(url)
            logger.debug(
                "Datadog API response",
                status_code=response.status_code,
                url=str(response.url),
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Datadog dashboards fetched",
                dashboard_count=len(data.get("dashboards", [])),
            )
            return data
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if e.response else "No response"
            logger.error(
                "Datadog API HTTP error",
                status_code=e.response.status_code if e.response else None,
                url=url,
                error=error_text[:500],
            )
            raise
        except Exception as e:
            logger.error("Datadog API request failed", url=url, error=str(e))
            raise

    async def get_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Get dashboard by ID."""
        url = f"/v1/dashboard/{dashboard_id}"
        logger.debug("Calling Datadog API", url=url, base_url=self.base_url)
        try:
            response = await self._client.get(url)
            logger.debug(
                "Datadog API response",
                status_code=response.status_code,
                url=str(response.url),
            )
            response.raise_for_status()
            data = response.json()
            logger.info("Datadog dashboard fetched", dashboard_id=dashboard_id)
            return data
        except httpx.HTTPStatusError as e:
            if e.response and e.response.status_code == 404:
                error_text = e.response.text if e.response else "No response"
                logger.warning(
                    "Datadog dashboard not found",
                    dashboard_id=dashboard_id,
                    status_code=404,
                    error=error_text[:500],
                )
                raise
            error_text = e.response.text if e.response else "No response"
            logger.error(
                "Datadog API HTTP error",
                status_code=e.response.status_code if e.response else None,
                url=url,
                error=error_text[:500],
            )
            raise
        except Exception as e:
            logger.error("Datadog API request failed", url=url, error=str(e))
            raise

    # ==================== Monitor APIs ====================

    async def list_monitors(
        self,
        tags: Optional[List[str]] = None,
        page: int = 0,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all monitors."""
        params = {
            "page": page,
            "page_size": page_size,
        }
        if tags:
            params["monitor_tags"] = ",".join(tags)
        
        response = await self._client.get("/v1/monitor", params=params)
        response.raise_for_status()
        return response.json()

    async def get_monitor(self, monitor_id: int) -> Dict[str, Any]:
        """Get monitor by ID."""
        response = await self._client.get(f"/v1/monitor/{monitor_id}")
        response.raise_for_status()
        return response.json()

    # ==================== Metrics APIs ====================

    async def query_metrics(
        self,
        query: str,
        start: int,
        end: int,
    ) -> Dict[str, Any]:
        """
        Query time series data.
        
        Args:
            query: Datadog metrics query
            start: Start timestamp (Unix seconds)
            end: End timestamp (Unix seconds)
        """
        params = {
            "query": query,
            "from": start,
            "to": end,
        }
        response = await self._client.get("/v1/query", params=params)
        response.raise_for_status()
        return response.json()

    async def list_metrics(self, query: Optional[str] = None) -> Dict[str, Any]:
        """List available metrics."""
        params = {}
        if query:
            params["q"] = query
        response = await self._client.get("/v1/metrics", params=params)
        response.raise_for_status()
        return response.json()

    async def get_metric_metadata(self, metric_name: str) -> Dict[str, Any]:
        """Get metadata for a specific metric."""
        response = await self._client.get(f"/v1/metrics/{metric_name}")
        response.raise_for_status()
        return response.json()

    async def list_active_metrics(
        self,
        from_timestamp: int,
        host: Optional[str] = None,
        tag_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List active metrics since a given time."""
        params = {"from": from_timestamp}
        if host:
            params["host"] = host
        if tag_filter:
            params["tag_filter"] = tag_filter
        
        response = await self._client.get("/v1/metrics", params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Tags APIs ====================

    async def query_tag_values(
        self,
        metric_name: str,
        tag_key: str,
        lookback_seconds: int = 14400,
    ) -> List[str]:
        """
        Query a metric grouped by a tag key to discover distinct tag values.

        Uses ``GET /v1/query`` with ``avg:<metric>{*} by {<tag_key>}`` over
        a recent time window.  Returns a sorted list of unique tag values.

        Args:
            metric_name: Fully qualified metric name (e.g. ``aws.dynamodb.consumed_read_capacity_units``)
            tag_key: Tag key to group by (e.g. ``tablename``)
            lookback_seconds: How far back to query (default 4 hours)

        Returns:
            Sorted list of unique tag values discovered in the series.
        """
        import time

        now = int(time.time())
        start = now - lookback_seconds

        query = f"avg:{metric_name}{{*}} by {{{tag_key}}}"
        logger.debug(
            "Querying metric for tag values",
            metric=metric_name,
            tag_key=tag_key,
            query=query,
            lookback_seconds=lookback_seconds,
        )

        try:
            result = await self.query_metrics(query=query, start=start, end=now)
            series = result.get("series", [])

            values: set = set()
            for s in series:
                for tag in s.get("tag_set", []):
                    if tag.startswith(f"{tag_key}:"):
                        values.add(tag.split(":", 1)[1])

            logger.info(
                "Tag values discovered from metric query",
                metric=metric_name,
                tag_key=tag_key,
                value_count=len(values),
            )
            return sorted(values)
        except Exception as e:
            logger.warning(
                "Failed to query metric for tag values",
                metric=metric_name,
                tag_key=tag_key,
                error=str(e),
            )
            return []

    async def list_host_tags(self, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all host tags (GET /api/v1/tags/hosts).
        
        Returns a mapping of tag key:value strings to lists of hosts.
        Example response:
        {
            "tags": {
                "env:production": ["host1", "host2"],
                "service:web": ["host3"],
                ...
            }
        }
        
        Args:
            source: Optional filter by tag source (e.g., "datadog", "chef", "puppet")
        """
        params = {}
        if source:
            params["source"] = source
        url = "/v1/tags/hosts"
        logger.debug("Calling Datadog Tags API", url=url, base_url=self.base_url)
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            tag_count = len(data.get("tags", {}))
            logger.info("Datadog host tags fetched", tag_count=tag_count)
            return data
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if e.response else "No response"
            logger.error(
                "Datadog Tags API HTTP error",
                status_code=e.response.status_code if e.response else None,
                url=url,
                error=error_text[:500],
            )
            raise
        except Exception as e:
            logger.error("Datadog Tags API request failed", url=url, error=str(e))
            raise


