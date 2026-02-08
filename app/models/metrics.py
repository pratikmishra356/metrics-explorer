"""Universal metrics models following OpenTelemetry semantic conventions."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MetricType(str, Enum):
    """Metric types following OTel conventions."""

    GAUGE = "gauge"
    SUM = "sum"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AggregationTemporality(str, Enum):
    """Aggregation temporality for sum/histogram metrics."""

    UNSPECIFIED = "unspecified"
    DELTA = "delta"
    CUMULATIVE = "cumulative"


class ResourceAttributes(BaseModel):
    """
    Resource attributes following OTel semantic conventions.
    See: https://opentelemetry.io/docs/specs/semconv/resource/
    """

    # Service attributes
    service_name: Optional[str] = Field(None, alias="service.name")
    service_namespace: Optional[str] = Field(None, alias="service.namespace")
    service_instance_id: Optional[str] = Field(None, alias="service.instance.id")
    service_version: Optional[str] = Field(None, alias="service.version")

    # Deployment attributes
    deployment_environment: Optional[str] = Field(None, alias="deployment.environment")

    # Host attributes
    host_name: Optional[str] = Field(None, alias="host.name")
    host_id: Optional[str] = Field(None, alias="host.id")
    host_type: Optional[str] = Field(None, alias="host.type")

    # Cloud attributes
    cloud_provider: Optional[str] = Field(None, alias="cloud.provider")
    cloud_region: Optional[str] = Field(None, alias="cloud.region")
    cloud_availability_zone: Optional[str] = Field(None, alias="cloud.availability_zone")

    # Container attributes
    container_name: Optional[str] = Field(None, alias="container.name")
    container_id: Optional[str] = Field(None, alias="container.id")
    container_image_name: Optional[str] = Field(None, alias="container.image.name")

    # K8s attributes
    k8s_namespace_name: Optional[str] = Field(None, alias="k8s.namespace.name")
    k8s_pod_name: Optional[str] = Field(None, alias="k8s.pod.name")
    k8s_deployment_name: Optional[str] = Field(None, alias="k8s.deployment.name")

    # Additional custom attributes
    custom: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
        extra = "allow"


class MetricDataPoint(BaseModel):
    """
    Single data point following OTel NumberDataPoint/HistogramDataPoint conventions.
    """

    # Timestamps (Unix nanoseconds in OTel, but we use ISO strings for JSON)
    start_time: Optional[datetime] = Field(
        None, description="Start time of the measurement interval"
    )
    time: datetime = Field(..., description="Time when the measurement was taken")

    # Value - can be int, float, or histogram buckets
    value: Union[int, float, Dict[str, Any]] = Field(
        ..., description="Metric value"
    )

    # Attributes (labels/tags in other systems)
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Metric attributes/labels"
    )

    # Exemplars (optional trace context)
    exemplars: List[Dict[str, Any]] = Field(
        default_factory=list, description="Exemplar data points with trace context"
    )


class Metric(BaseModel):
    """
    Metric definition following OTel Metric conventions.
    """

    # Metric identity
    name: str = Field(..., description="Metric name")
    description: Optional[str] = Field(None, description="Human-readable description")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'ms', 'bytes')")

    # Metric type
    metric_type: MetricType = Field(..., description="Type of metric")
    
    # For sum metrics
    aggregation_temporality: Optional[AggregationTemporality] = Field(
        None, description="Aggregation temporality for sum/histogram"
    )
    is_monotonic: Optional[bool] = Field(
        None, description="Whether the sum is monotonically increasing"
    )

    # Data points
    data_points: List[MetricDataPoint] = Field(
        default_factory=list, description="Metric data points"
    )

    # Resource context
    resource: ResourceAttributes = Field(
        default_factory=ResourceAttributes, description="Resource attributes"
    )

    # Provider metadata
    provider_source: str = Field(..., description="Source provider (datadog, prometheus, grafana)")
    provider_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )


class MetricQuery(BaseModel):
    """Query model for fetching metrics."""

    # Metric selection
    metric_names: Optional[List[str]] = Field(
        None, description="Specific metric names to query"
    )
    metric_name_pattern: Optional[str] = Field(
        None, description="Regex pattern for metric names"
    )

    # Time range
    start_time: datetime = Field(..., description="Query start time")
    end_time: datetime = Field(..., description="Query end time")

    # Filtering by attributes
    attribute_filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filter by attribute key-value pairs",
    )

    # Resource filters
    resource_filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filter by resource attributes",
    )

    # Aggregation
    aggregation: Optional[str] = Field(
        None,
        description="Aggregation function (avg, sum, min, max, count)",
    )
    group_by: List[str] = Field(
        default_factory=list,
        description="Attributes to group by",
    )

    # Step/interval for time series
    step_seconds: Optional[int] = Field(
        None, description="Step interval in seconds for time series"
    )

    # Pagination
    limit: int = Field(default=1000, description="Maximum number of data points")
    offset: int = Field(default=0, description="Offset for pagination")


class MetricQueryResult(BaseModel):
    """Result of a metric query."""

    metrics: List[Metric] = Field(default_factory=list)
    
    # Query metadata
    query: MetricQuery
    total_count: int = Field(0, description="Total number of metrics matching query")
    
    # Timing
    query_time_ms: int = Field(0, description="Query execution time in milliseconds")
    
    # Provider info
    providers_queried: List[str] = Field(
        default_factory=list, description="Providers that were queried"
    )


class MetricMetadata(BaseModel):
    """Metadata about available metrics."""

    name: str
    description: Optional[str] = None
    unit: Optional[str] = None
    metric_type: MetricType
    
    # Available attributes/labels
    available_attributes: List[str] = Field(
        default_factory=list, description="Known attribute keys for this metric"
    )
    
    # Provider source
    provider_source: str
    
    # Additional info
    help_text: Optional[str] = None
    
    class Config:
        from_attributes = True


class MetricMetadataList(BaseModel):
    """List of metric metadata."""
    
    metrics: List[MetricMetadata] = Field(default_factory=list)
    total_count: int = 0
    providers_queried: List[str] = Field(default_factory=list)
