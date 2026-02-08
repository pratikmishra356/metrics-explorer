"""Grafana API client for metrics exploration."""

from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class GrafanaClient:
    """HTTP client for Grafana API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
    ):
        """
        Initialize Grafana client.
        
        Args:
            base_url: Grafana server URL
            api_key: Grafana API key or service account token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
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

    async def search_dashboards(
        self,
        query: Optional[str] = None,
        tag: Optional[List[str]] = None,
        folder_ids: Optional[List[int]] = None,
        type_: str = "dash-db",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search for dashboards."""
        params = {"type": type_, "limit": limit}
        if query:
            params["query"] = query
        if tag:
            params["tag"] = tag
        if folder_ids:
            params["folderIds"] = folder_ids
        
        response = await self._client.get("/api/search", params=params)
        response.raise_for_status()
        return response.json()

    async def get_dashboard_by_uid(self, uid: str) -> Dict[str, Any]:
        """Get dashboard by UID."""
        response = await self._client.get(f"/api/dashboards/uid/{uid}")
        response.raise_for_status()
        return response.json()

    async def get_dashboard_by_id(self, dashboard_id: int) -> Dict[str, Any]:
        """Get dashboard by ID."""
        response = await self._client.get(f"/api/dashboards/id/{dashboard_id}")
        response.raise_for_status()
        return response.json()

    # ==================== Folder APIs ====================

    async def list_folders(self) -> List[Dict[str, Any]]:
        """List all folders."""
        response = await self._client.get("/api/folders")
        response.raise_for_status()
        return response.json()

    async def get_folder(self, uid: str) -> Dict[str, Any]:
        """Get folder by UID."""
        response = await self._client.get(f"/api/folders/{uid}")
        response.raise_for_status()
        return response.json()

    # ==================== Alert APIs ====================

    async def list_alert_rules(self) -> Dict[str, Any]:
        """List all alert rules (Grafana 8+ unified alerting)."""
        response = await self._client.get("/api/v1/provisioning/alert-rules")
        response.raise_for_status()
        return response.json()

    async def get_alert_rule(self, uid: str) -> Dict[str, Any]:
        """Get alert rule by UID."""
        response = await self._client.get(f"/api/v1/provisioning/alert-rules/{uid}")
        response.raise_for_status()
        return response.json()

    async def list_alerts(self) -> Dict[str, Any]:
        """List current alerts."""
        response = await self._client.get("/api/alertmanager/grafana/api/v2/alerts")
        response.raise_for_status()
        return response.json()

    async def list_legacy_alerts(self) -> List[Dict[str, Any]]:
        """List legacy alerts (Grafana 7 and earlier)."""
        response = await self._client.get("/api/alerts")
        response.raise_for_status()
        return response.json()

    # ==================== Datasource APIs ====================

    async def list_datasources(self) -> List[Dict[str, Any]]:
        """List all datasources."""
        response = await self._client.get("/api/datasources")
        response.raise_for_status()
        return response.json()

    async def get_datasource(self, datasource_id: int) -> Dict[str, Any]:
        """Get datasource by ID."""
        response = await self._client.get(f"/api/datasources/{datasource_id}")
        response.raise_for_status()
        return response.json()

    async def get_datasource_by_uid(self, uid: str) -> Dict[str, Any]:
        """Get datasource by UID."""
        response = await self._client.get(f"/api/datasources/uid/{uid}")
        response.raise_for_status()
        return response.json()

    # ==================== Query APIs ====================

    async def query_datasource(
        self,
        datasource_uid: str,
        queries: List[Dict[str, Any]],
        from_time: str,
        to_time: str,
    ) -> Dict[str, Any]:
        """
        Query a datasource.
        
        Args:
            datasource_uid: Datasource UID
            queries: List of query objects
            from_time: Start time (ISO format or relative like "now-1h")
            to_time: End time (ISO format or relative like "now")
        """
        payload = {
            "queries": queries,
            "from": from_time,
            "to": to_time,
        }
        response = await self._client.post("/api/ds/query", json=payload)
        response.raise_for_status()
        return response.json()

    # ==================== Annotation APIs ====================

    async def list_annotations(
        self,
        from_time: Optional[int] = None,
        to_time: Optional[int] = None,
        dashboard_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List annotations."""
        params = {"limit": limit}
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        if dashboard_id:
            params["dashboardId"] = dashboard_id
        if tags:
            params["tags"] = tags
        
        response = await self._client.get("/api/annotations", params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Health APIs ====================

    async def health(self) -> Dict[str, Any]:
        """Check Grafana health."""
        response = await self._client.get("/api/health")
        response.raise_for_status()
        return response.json()

    async def get_org(self) -> Dict[str, Any]:
        """Get current organization."""
        response = await self._client.get("/api/org")
        response.raise_for_status()
        return response.json()
