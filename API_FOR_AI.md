# Metrics Explorer API - Guide for AI Agents

Provider-agnostic metrics exploration API that connects to Datadog, Prometheus, and Grafana.

## Base URL

```
http://localhost:8002/api/v1
```

## Core Concepts

- **Organization**: Top-level tenant container (has providers, dashboards)
- **Dashboard**: A collection of metric widgets synced from a provider
- **Metric (Widget)**: An extracted metric query from a dashboard widget
- **Template Variable**: A tag key with resolved values (e.g., `$tablename` with 1700+ table names)
- **Used Dashboards**: Important dashboards marked by users — **check these first**

## Quick Workflow

1. Get organization → Check `used_dashboards` for important dashboards
2. Search dashboards → Find dashboards matching a pattern
3. Search metrics → Find metrics within a dashboard
4. Get variable values → Understand available filter values
5. Query metrics → Execute metric queries with filters

## Key APIs

### 1. Get Organization (Check Used Dashboards)

```
GET /organizations/{org_id}
```

**Response** includes `used_dashboards: ["4k2-qvg-h38", "abc-123"]` — prioritize these dashboards first.

### 2. Get Used Dashboards (with details)

```
GET /organizations/{org_id}/used-dashboards
```

**Response**:
```json
{
  "dashboard_ids": ["4k2-qvg-h38"],
  "used_dashboards": [
    {
      "id": "db-uuid",
      "dashboard_id": "4k2-qvg-h38",
      "title": "[OPS] DynamoDB Table Utilization",
      "provider_type": "datadog"
    }
  ],
  "total_count": 1
}
```

### 3. Search Dashboards (Wildcard)

```
GET /organizations/{org_id}/dashboards/search?search=DynamoDB*
GET /organizations/{org_id}/dashboards/search
```

**Note**: `search` parameter is **optional**. If omitted, returns all dashboards.

Space-separated terms = OR search. Supports `*` wildcard.

**Response**:
```json
{
  "dashboards": [
    {
      "id": "db-uuid",
      "dashboard_id": "4k2-qvg-h38",
      "title": "[OPS] DynamoDB Table Utilization",
      "provider_type": "datadog"
    }
  ],
  "total_count": 1
}
```

### 4. Search Metrics in a Dashboard (Wildcard)

```
GET /organizations/{org_id}/dashboards/{dashboard_db_id}/metrics/search?search=dynamodb*consumed
GET /organizations/{org_id}/dashboards/{dashboard_db_id}/metrics/search
```

**Note**: `search` parameter is **optional**. If omitted, returns all metrics for the dashboard.

**Response**:
```json
{
  "metrics": [
    {
      "id": "metric-uuid",
      "widget_id": "12345",
      "name": "aws.dynamodb.consumed_read_capacity_units",
      "description": "timeseries widget with 1 query",
      "provider": "datadog",
      "details": { "widget_type": "timeseries", "requests": [...] }
    }
  ],
  "total_count": 1
}
```

### 5. Get Template Variable Values

```
GET /organizations/{org_id}/dashboards/{dashboard_db_id}/variables/{variable_name}/values
GET /organizations/{org_id}/dashboards/{dashboard_db_id}/variables/tablename/values?search=prod
```

**Response**:
```json
{
  "variable_name": "tablename",
  "tag_key": "tablename",
  "default_value": "*",
  "values": ["prod-contact-management-audit", "prod-contact-management-contacts", ...],
  "total_count": 1742,
  "returned_count": 200
}
```

### 6. List Template Variables for a Dashboard

```
GET /organizations/{org_id}/template-variables?dashboard_id={dashboard_db_id}
```

**Response**: All variables for a dashboard with their resolved values.

### 7. Query Metrics (Execute)

```
POST /dashboards/{dashboard_id}/query
Headers: X-Organization-Id: {org_id}
```

**Body**:
```json
{
  "queries": [
    {
      "metric_name": "aws.dynamodb.consumed_read_capacity_units",
      "aggregation": "avg",
      "filters": {
        "tablename": "prod-contact-management-audit",
        "toast_environment": "prod"
      },
      "group_by": ["tablename"]
    }
  ],
  "time_range": { "relative": "1h" }
}
```

**Notes**:
- `filters` are optional — omit to query all values (wildcard)
- `filters` values can be a string or an array (OR semantics): `"tablename": ["table1", "table2"]`
- `aggregation`: `avg`, `sum`, `min`, `max`, `count`, `last`
- `time_range.relative`: `"15m"`, `"1h"`, `"4h"`, `"24h"`, `"7d"`
- `time_range.start` / `time_range.end`: Unix epoch seconds (alternative to relative)
- `group_by`: tag keys to group results by

**Response**:
```json
{
  "dashboard_id": "4k2-qvg-h38",
  "provider": "datadog",
  "results": [
    {
      "query_index": 0,
      "metric_name": "aws.dynamodb.consumed_read_capacity_units",
      "expression": "avg:aws.dynamodb.consumed_read_capacity_units{tablename:prod-contact-management-audit} by {tablename}",
      "series": [
        {
          "scope": "tablename:prod-contact-management-audit",
          "tags": { "tablename": "prod-contact-management-audit" },
          "datapoints": [
            { "timestamp": 1770484140000, "value": 0.0 }
          ],
          "unit": "unit"
        }
      ],
      "series_count": 1,
      "datapoint_count": 48,
      "query_time_ms": 1276
    }
  ],
  "total_queries": 1,
  "total_series": 1,
  "total_datapoints": 48,
  "execution_time_ms": 1276
}
```

### 8. Sync Dashboards from Provider

```
POST /dashboards/sync
Headers: X-Organization-Id: {org_id}
```

### 9. Extract Metrics from a Dashboard

```
POST /dashboards/{provider_dashboard_id}/extract-metrics
Headers: X-Organization-Id: {org_id}
```

Extracts all widget metric queries and resolves template variables.

## Using Used Dashboards

```python
# 1. Get org and check used_dashboards
org = GET /organizations/{org_id}
important_ids = org.used_dashboards  # ["4k2-qvg-h38"]

# 2. Get full details for those dashboards
used = GET /organizations/{org_id}/used-dashboards
for dash in used.used_dashboards:
    dashboard_db_id = dash.id
    # Explore this dashboard first
```

## Example Workflow

```python
# 1. Get organization — check used_dashboards
org = GET /organizations/{org_id}
used_ids = org.used_dashboards  # ["4k2-qvg-h38"]

# 2. Search for DynamoDB dashboards
results = GET /organizations/{org_id}/dashboards/search?search=DynamoDB
dashboard = results.dashboards[0]  # id = "db-uuid", dashboard_id = "4k2-qvg-h38"

# 3. Search metrics within that dashboard
metrics = GET /organizations/{org_id}/dashboards/{dashboard.id}/metrics/search?search=consumed*read
# Found: aws.dynamodb.consumed_read_capacity_units

# 4. Check what table names are available
values = GET /organizations/{org_id}/dashboards/{dashboard.id}/variables/tablename/values?search=prod
# Returns 200 table names matching "prod"

# 5. Query the metric with a filter
result = POST /dashboards/4k2-qvg-h38/query
         Headers: X-Organization-Id: {org_id}
         Body: {
           "queries": [{
             "metric_name": "aws.dynamodb.consumed_read_capacity_units",
             "aggregation": "avg",
             "filters": {"tablename": "prod-contact-management-audit"},
             "group_by": ["tablename"]
           }],
           "time_range": {"relative": "1h"}
         }
```

## Tips

- **Check `used_dashboards` first** — these are the important dashboards
- **Use wildcard search** (`*DynamoDB*`) to find dashboards and metrics quickly
- **Use variable values endpoint** to discover available filter values before querying
- **Use `search` parameter** on variable values to narrow high-cardinality variables
- **Set reasonable time ranges** — smaller ranges return faster
- **Use `group_by`** to break down metrics by tags
- **Filters are optional** — omit to get aggregate data, add to narrow down

## Error Codes

- `404`: Organization / dashboard / variable not found
- `400`: Invalid request (e.g., bad aggregation)
- `502`: Provider query execution failed
- `500`: Internal server error
