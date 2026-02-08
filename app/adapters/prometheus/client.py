"""Prometheus API client for metrics exploration."""

from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PrometheusClient:
    """HTTP client for Prometheus API."""

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        bearer_token: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize Prometheus client.
        
        Args:
            base_url: Prometheus server URL
            username: Basic auth username
            password: Basic auth password
            bearer_token: Bearer token for auth
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        # Set up authentication
        auth = None
        headers = {"Content-Type": "application/json"}
        
        if username and password:
            auth = (username, password)
        elif bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            headers=headers,
            timeout=timeout,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ==================== Query APIs ====================

    async def instant_query(
        self,
        query: str,
        time: Optional[float] = None,
        timeout: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute an instant query.
        
        Args:
            query: PromQL query
            time: Evaluation timestamp (Unix seconds)
            timeout: Evaluation timeout
        """
        params = {"query": query}
        if time:
            params["time"] = time
        if timeout:
            params["timeout"] = timeout
        
        response = await self._client.get("/api/v1/query", params=params)
        response.raise_for_status()
        return response.json()

    async def range_query(
        self,
        query: str,
        start: float,
        end: float,
        step: str = "60s",
        timeout: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a range query.
        
        Args:
            query: PromQL query
            start: Start timestamp (Unix seconds)
            end: End timestamp (Unix seconds)
            step: Query resolution step (e.g., "60s", "5m")
            timeout: Evaluation timeout
        """
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        if timeout:
            params["timeout"] = timeout
        
        response = await self._client.get("/api/v1/query_range", params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Metadata APIs ====================

    async def list_label_names(
        self,
        start: Optional[float] = None,
        end: Optional[float] = None,
        match: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List all label names."""
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if match:
            params["match[]"] = match
        
        response = await self._client.get("/api/v1/labels", params=params)
        response.raise_for_status()
        return response.json()

    async def list_label_values(
        self,
        label_name: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
        match: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List values for a label."""
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if match:
            params["match[]"] = match
        
        response = await self._client.get(
            f"/api/v1/label/{label_name}/values", params=params
        )
        response.raise_for_status()
        return response.json()

    async def list_series(
        self,
        match: List[str],
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> Dict[str, Any]:
        """List time series matching a selector."""
        params = {"match[]": match}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        
        response = await self._client.get("/api/v1/series", params=params)
        response.raise_for_status()
        return response.json()

    async def get_metadata(
        self,
        metric: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get metric metadata."""
        params = {}
        if metric:
            params["metric"] = metric
        if limit:
            params["limit"] = limit
        
        response = await self._client.get("/api/v1/metadata", params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Target/Rules APIs ====================

    async def list_targets(self, state: Optional[str] = None) -> Dict[str, Any]:
        """List all scrape targets."""
        params = {}
        if state:
            params["state"] = state
        
        response = await self._client.get("/api/v1/targets", params=params)
        response.raise_for_status()
        return response.json()

    async def list_rules(self, type: Optional[str] = None) -> Dict[str, Any]:
        """List alerting and recording rules."""
        params = {}
        if type:
            params["type"] = type
        
        response = await self._client.get("/api/v1/rules", params=params)
        response.raise_for_status()
        return response.json()

    async def list_alerts(self) -> Dict[str, Any]:
        """List active alerts."""
        response = await self._client.get("/api/v1/alerts")
        response.raise_for_status()
        return response.json()

    # ==================== Health APIs ====================

    async def health(self) -> bool:
        """Check Prometheus health."""
        try:
            response = await self._client.get("/-/healthy")
            return response.status_code == 200
        except Exception:
            return False

    async def ready(self) -> bool:
        """Check Prometheus readiness."""
        try:
            response = await self._client.get("/-/ready")
            return response.status_code == 200
        except Exception:
            return False
