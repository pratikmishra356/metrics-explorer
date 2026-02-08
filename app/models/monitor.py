"""Universal monitor/alert models following OpenTelemetry conventions."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.metrics import ResourceAttributes


class MonitorStatus(str, Enum):
    """Monitor status states."""

    OK = "ok"
    WARNING = "warning"
    ALERT = "alert"
    NO_DATA = "no_data"
    UNKNOWN = "unknown"
    MUTED = "muted"


class MonitorType(str, Enum):
    """Types of monitors."""

    METRIC = "metric"
    LOG = "log"
    APM = "apm"
    SYNTHETICS = "synthetics"
    COMPOSITE = "composite"
    PROCESS = "process"
    NETWORK = "network"
    ANOMALY = "anomaly"
    FORECAST = "forecast"
    OUTLIER = "outlier"
    OTHER = "other"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MonitorThreshold(BaseModel):
    """Threshold configuration for a monitor."""

    comparison: str = Field(
        ..., description="Comparison operator (>, <, >=, <=, ==, !=)"
    )
    value: float = Field(..., description="Threshold value")
    severity: AlertSeverity = Field(
        default=AlertSeverity.MEDIUM, description="Severity when threshold is breached"
    )
    
    # Duration requirements
    duration_seconds: Optional[int] = Field(
        None, description="Duration threshold must be breached"
    )
    
    # Recovery settings
    recovery_value: Optional[float] = Field(
        None, description="Value at which to recover"
    )


class MonitorQuery(BaseModel):
    """Query definition for a monitor."""

    # Query identifier
    query_id: str = Field(..., description="Query identifier")
    
    # Query expression (original format preserved)
    raw_query: str = Field(..., description="Original query in provider format")
    
    # Normalized info
    metric_names: List[str] = Field(
        default_factory=list, description="Metric names referenced"
    )
    aggregation: Optional[str] = Field(None, description="Aggregation function")
    group_by: List[str] = Field(default_factory=list, description="Grouping dimensions")
    
    # Time window
    evaluation_window_seconds: Optional[int] = Field(
        None, description="Time window for evaluation"
    )


class MonitorNotification(BaseModel):
    """Notification configuration for a monitor."""

    channel_type: str = Field(
        ..., description="Notification channel type (email, slack, pagerduty, etc.)"
    )
    channel_id: Optional[str] = Field(None, description="Channel identifier")
    
    # Message templates
    message_template: Optional[str] = Field(
        None, description="Message template for notifications"
    )
    
    # Notification settings
    notify_on_ok: bool = Field(
        default=True, description="Notify when recovered to OK"
    )
    notify_on_no_data: bool = Field(
        default=True, description="Notify when no data"
    )
    
    # Provider-specific config
    provider_config: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific notification config"
    )


class MonitorStateTransition(BaseModel):
    """Record of a monitor state transition."""

    from_status: MonitorStatus
    to_status: MonitorStatus
    timestamp: datetime
    trigger_value: Optional[float] = None
    message: Optional[str] = None


class Monitor(BaseModel):
    """
    Universal monitor model using OTel resource concepts.
    """

    # Monitor identity
    id: str = Field(..., description="Monitor identifier (provider-specific)")
    name: str = Field(..., description="Monitor name")
    description: Optional[str] = Field(None, description="Monitor description")

    # Resource attributes (OTel concept for context)
    resource: ResourceAttributes = Field(
        default_factory=ResourceAttributes,
        description="Resource attributes for monitor context",
    )

    # Monitor configuration
    monitor_type: MonitorType = Field(..., description="Type of monitor")
    queries: List[MonitorQuery] = Field(
        default_factory=list, description="Queries that define the monitor"
    )
    thresholds: List[MonitorThreshold] = Field(
        default_factory=list, description="Threshold configurations"
    )

    # Current state
    status: MonitorStatus = Field(
        default=MonitorStatus.UNKNOWN, description="Current monitor status"
    )
    current_value: Optional[float] = Field(
        None, description="Current metric value"
    )
    last_evaluated_at: Optional[datetime] = Field(
        None, description="Last evaluation timestamp"
    )
    last_triggered_at: Optional[datetime] = Field(
        None, description="Last alert trigger timestamp"
    )

    # State history (recent transitions)
    recent_state_changes: List[MonitorStateTransition] = Field(
        default_factory=list, description="Recent state transitions"
    )

    # Notification configuration
    notifications: List[MonitorNotification] = Field(
        default_factory=list, description="Notification channels"
    )

    # Monitor metadata
    tags: List[str] = Field(default_factory=list, description="Monitor tags/labels")
    priority: Optional[AlertSeverity] = Field(
        None, description="Default priority/severity"
    )
    
    # Muting/silencing
    is_muted: bool = Field(default=False, description="Whether monitor is muted")
    mute_until: Optional[datetime] = Field(
        None, description="Mute until timestamp"
    )

    # Ownership
    created_by: Optional[str] = Field(None, description="Creator identifier")
    modified_by: Optional[str] = Field(None, description="Last modifier identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")

    # URLs
    url: Optional[str] = Field(None, description="Direct URL to monitor in provider")

    # Provider metadata
    provider_source: str = Field(..., description="Source provider")
    provider_monitor_type: Optional[str] = Field(
        None, description="Monitor type in provider"
    )
    provider_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )

    class Config:
        from_attributes = True


class MonitorSummary(BaseModel):
    """Summary view of a monitor (for list endpoints)."""

    id: str
    name: str
    description: Optional[str] = None
    monitor_type: MonitorType
    status: MonitorStatus
    priority: Optional[AlertSeverity] = None
    tags: List[str] = Field(default_factory=list)
    is_muted: bool = False
    last_triggered_at: Optional[datetime] = None
    url: Optional[str] = None
    provider_source: str

    class Config:
        from_attributes = True


class MonitorList(BaseModel):
    """List of monitors response."""

    monitors: List[MonitorSummary] = Field(default_factory=list)
    total_count: int = 0
    providers_queried: List[str] = Field(default_factory=list)
    
    # Summary statistics
    status_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of monitors by status"
    )
