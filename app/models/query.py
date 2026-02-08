"""
Provider-agnostic models for dashboard metric querying.

These models define the universal request/response contract used by the
``POST /dashboards/{dashboard_id}/query`` endpoint.  The same shape is
accepted regardless of the underlying provider (Datadog, Prometheus, Grafana).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────────────
#  Request models
# ──────────────────────────────────────────────────────────────────────


class TimeRange(BaseModel):
    """
    Time range for the query.

    Either supply explicit ``start`` / ``end`` Unix-epoch seconds **or**
    a ``relative`` duration string like ``"1h"``, ``"24h"``, ``"7d"``.
    When *relative* is given, *start* and *end* are ignored.
    """

    start: Optional[int] = Field(
        None, description="Start time as Unix epoch seconds"
    )
    end: Optional[int] = Field(
        None, description="End time as Unix epoch seconds"
    )
    relative: Optional[str] = Field(
        None,
        description="Relative duration (e.g. '1h', '4h', '24h', '7d')",
    )

    def resolve(self) -> tuple[int, int]:
        """Return (start, end) as Unix-epoch seconds."""
        import time as _time

        now = int(_time.time())

        if self.relative:
            seconds = self._parse_relative(self.relative)
            return now - seconds, now

        return (self.start or (now - 3600)), (self.end or now)

    @staticmethod
    def _parse_relative(value: str) -> int:
        """Convert ``'1h'``, ``'24h'``, ``'7d'`` etc. to seconds."""
        value = value.strip().lower()
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        for suffix, mult in multipliers.items():
            if value.endswith(suffix):
                try:
                    return int(value[: -len(suffix)]) * mult
                except ValueError:
                    break
        # Fallback: 1 hour
        return 3600


class MetricQueryItem(BaseModel):
    """
    A single metric query within a batch request.

    ``filters`` carries template-variable values or any tag filters.
    Values can be a single string or a list of strings (OR semantics).
    """

    metric_name: str = Field(
        ..., description="Fully qualified metric name, e.g. 'aws.dynamodb.consumed_read_capacity_units'"
    )
    aggregation: str = Field(
        "avg", description="Aggregation function: avg, sum, min, max, count, last"
    )
    filters: Dict[str, Union[str, List[str]]] = Field(
        default_factory=dict,
        description=(
            "Tag/variable filters. Keys are tag names (e.g. 'tablename', 'env'). "
            "Values can be a single string or a list (OR). "
            "Omit a key to leave that variable unfiltered (wildcard)."
        ),
    )
    group_by: List[str] = Field(
        default_factory=list,
        description="Tag keys to group results by",
    )
    limit: Optional[int] = Field(
        None, description="Max number of series to return (provider may cap this)"
    )

    @field_validator("aggregation")
    @classmethod
    def _validate_aggregation(cls, v: str) -> str:
        allowed = {"avg", "sum", "min", "max", "count", "last", "p50", "p75", "p90", "p95", "p99"}
        if v.lower() not in allowed:
            raise ValueError(f"aggregation must be one of {allowed}")
        return v.lower()


class DashboardQueryRequest(BaseModel):
    """
    Batch request to query metrics for a dashboard.

    The caller provides one or more ``MetricQueryItem`` entries together
    with a shared ``TimeRange``.  Variable filters are **optional** —
    omitting a variable means "all values" (wildcard).
    """

    queries: List[MetricQueryItem] = Field(
        ..., min_length=1, description="List of metric queries to execute"
    )
    time_range: TimeRange = Field(
        default_factory=lambda: TimeRange(relative="1h"),
        description="Time range for all queries",
    )


# ──────────────────────────────────────────────────────────────────────
#  Response models
# ──────────────────────────────────────────────────────────────────────


class DataPoint(BaseModel):
    """Single time-series data point."""

    timestamp: int = Field(..., description="Unix epoch milliseconds")
    value: Optional[float] = Field(None, description="Metric value (null = no data)")


class Series(BaseModel):
    """
    One tagged series returned for a metric query.

    ``tags`` contains the key-value pairs identifying this particular
    series (e.g. ``{"tablename": "my-table", "env": "prod"}``).
    """

    scope: str = Field(
        "", description="Provider scope string (e.g. 'tablename:my-table')"
    )
    tags: Dict[str, str] = Field(
        default_factory=dict, description="Parsed tag key-value pairs"
    )
    datapoints: List[DataPoint] = Field(
        default_factory=list, description="Time-series data points"
    )
    unit: Optional[str] = Field(None, description="Unit of measurement")


class QueryResultItem(BaseModel):
    """Result for a single ``MetricQueryItem``."""

    query_index: int = Field(..., description="Index of the query in the request")
    metric_name: str
    display_name: Optional[str] = None
    expression: Optional[str] = Field(
        None, description="The raw provider query expression that was executed"
    )
    series: List[Series] = Field(default_factory=list)
    series_count: int = 0
    datapoint_count: int = 0
    query_time_ms: int = 0
    error: Optional[str] = Field(
        None, description="Error message if this query failed"
    )


class DashboardQueryResponse(BaseModel):
    """
    Response for a batch dashboard metric query.
    """

    dashboard_id: str
    provider: str
    results: List[QueryResultItem] = Field(default_factory=list)
    total_queries: int = 0
    total_series: int = 0
    total_datapoints: int = 0
    execution_time_ms: int = 0
