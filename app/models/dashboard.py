"""Universal dashboard models following OpenTelemetry conventions."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.metrics import ResourceAttributes


class WidgetType(str, Enum):
    """Types of dashboard widgets."""

    TIMESERIES = "timeseries"
    GAUGE = "gauge"
    TABLE = "table"
    TEXT = "text"
    ALERT_LIST = "alert_list"
    LOG_STREAM = "log_stream"
    HEATMAP = "heatmap"
    DISTRIBUTION = "distribution"
    TOPLIST = "toplist"
    PIE_CHART = "pie_chart"
    OTHER = "other"


class VisualizationType(str, Enum):
    """Visualization types for widgets."""

    LINE = "line"
    AREA = "area"
    BAR = "bar"
    STACKED_AREA = "stacked_area"
    STACKED_BAR = "stacked_bar"
    SCATTER = "scatter"
    SOLID_GAUGE = "solid_gauge"
    OTHER = "other"


class DashboardWidgetQuery(BaseModel):
    """Query definition within a widget."""

    # Query identifier
    query_id: str = Field(..., description="Unique identifier for this query")
    
    # Query expression (original provider format preserved)
    raw_query: str = Field(..., description="Original query in provider format")
    
    # Normalized query info
    metric_names: List[str] = Field(
        default_factory=list, description="Metric names referenced in query"
    )
    
    # Aggregation info
    aggregation: Optional[str] = Field(None, description="Aggregation function used")
    group_by: List[str] = Field(
        default_factory=list, description="Grouping dimensions"
    )
    
    # Display options
    display_name: Optional[str] = Field(None, description="Display name for legend")
    color: Optional[str] = Field(None, description="Color for this series")


class DashboardWidget(BaseModel):
    """
    Widget model following OTel-compatible structure.
    Maps provider-specific widgets to a common format.
    """

    # Widget identity
    id: str = Field(..., description="Widget identifier")
    title: str = Field(..., description="Widget title")
    description: Optional[str] = Field(None, description="Widget description")

    # Widget type and visualization
    widget_type: WidgetType = Field(..., description="Type of widget")
    visualization_type: Optional[VisualizationType] = Field(
        None, description="Visualization type"
    )

    # Position and sizing (normalized to percentage-based grid)
    position: Dict[str, float] = Field(
        default_factory=dict,
        description="Position {x, y, width, height} in percentage",
    )

    # Queries
    queries: List[DashboardWidgetQuery] = Field(
        default_factory=list, description="Data queries for this widget"
    )

    # Time range (if widget-specific)
    time_range: Optional[Dict[str, Any]] = Field(
        None, description="Widget-specific time range override"
    )

    # Thresholds and alerts
    thresholds: List[Dict[str, Any]] = Field(
        default_factory=list, description="Visual thresholds"
    )

    # Provider metadata
    provider_widget_type: str = Field(
        ..., description="Original widget type in provider"
    )
    provider_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )


class Dashboard(BaseModel):
    """
    Universal dashboard model using OTel resource concepts.
    """

    # Dashboard identity
    id: str = Field(..., description="Dashboard identifier (provider-specific)")
    title: str = Field(..., description="Dashboard title")
    description: Optional[str] = Field(None, description="Dashboard description")

    # Resource attributes (OTel concept for context)
    resource: ResourceAttributes = Field(
        default_factory=ResourceAttributes,
        description="Resource attributes for dashboard context",
    )

    # Widgets
    widgets: List[DashboardWidget] = Field(
        default_factory=list, description="Dashboard widgets"
    )

    # Dashboard metadata
    tags: List[str] = Field(default_factory=list, description="Dashboard tags/labels")
    folder: Optional[str] = Field(None, description="Folder/group containing dashboard")

    # Time settings
    default_time_range: Optional[Dict[str, Any]] = Field(
        None, description="Default time range for dashboard"
    )
    refresh_interval: Optional[str] = Field(
        None, description="Auto-refresh interval (e.g., '30s', '5m')"
    )

    # Ownership and access
    created_by: Optional[str] = Field(None, description="Creator identifier")
    modified_by: Optional[str] = Field(None, description="Last modifier identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")

    # URLs
    url: Optional[str] = Field(None, description="Direct URL to dashboard in provider")

    # Provider metadata
    provider_source: str = Field(..., description="Source provider")
    provider_dashboard_type: Optional[str] = Field(
        None, description="Dashboard type in provider"
    )
    provider_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    """Summary view of a dashboard (for list endpoints)."""

    id: str
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    folder: Optional[str] = None
    widget_count: int = 0
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    url: Optional[str] = None
    provider_source: str

    class Config:
        from_attributes = True


class DashboardList(BaseModel):
    """List of dashboards response."""

    dashboards: List[DashboardSummary] = Field(default_factory=list)
    total_count: int = 0
    providers_queried: List[str] = Field(default_factory=list)
