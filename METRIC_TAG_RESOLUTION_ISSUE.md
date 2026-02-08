# Metric Tag Resolution Issue: `tablename` Example

## Problem

Template variables like `$tablename` show "no values resolved" because:

1. **`tablename` is a metric tag**, not a host tag
2. **`/api/v1/tags/hosts` only returns host/infrastructure tags**
3. DynamoDB table names are tags on metrics (e.g., `aws.dynamodb.*` metrics), not on hosts

## Current Behavior

When resolving template variables:
1. ✅ Checks for `available_values` in dashboard JSON (if manually defined)
2. ✅ Falls back to `/api/v1/tags/hosts` (host tags only)
3. ❌ **No fallback for metric tags**

## Example: `$tablename` Variable

### Dashboard: "[OPS] DynamoDB Table Utilization"

**Template Variable Definition:**
```json
{
  "name": "tablename",
  "prefix": "tablename",
  "default": "*"
}
```

**What Happens:**
- No `available_values` defined
- `/api/v1/tags/hosts` doesn't contain `tablename:*` (it's a metric tag)
- Result: Empty values → "no values resolved"

## Solutions

### Solution 1: Use `available_values` (Recommended for Now)

Dashboard creators can manually define values in Datadog:

```json
{
  "name": "tablename",
  "prefix": "tablename",
  "default": "*",
  "available_values": [
    "users-table",
    "orders-table",
    "products-table",
    ...
  ]
}
```

**Pros:**
- ✅ Works immediately
- ✅ No additional API calls
- ✅ Dashboard creator controls the list

**Cons:**
- ❌ Manual maintenance
- ❌ Can get out of sync

### Solution 2: Query Metrics API (Future Enhancement)

Query DynamoDB metrics to extract tag values:

```python
# Pseudo-code
async def resolve_metric_tag_values(prefix: str, metric_pattern: str = None):
    # Query a sample metric (e.g., aws.dynamodb.consumed_read_capacity_units)
    # Extract tag values for the given prefix
    # Return unique values
```

**Pros:**
- ✅ Automatic discovery
- ✅ Always up-to-date

**Cons:**
- ❌ Requires knowing which metrics to query
- ❌ More API calls
- ❌ May hit rate limits

### Solution 3: Extract from Dashboard Widgets (Future Enhancement)

Parse widget queries to extract tag values:

```python
# If widgets have queries like:
# "avg:aws.dynamodb.consumed_read_capacity_units{tablename:*} by {tablename}"
# Extract the tag values from the query results
```

**Pros:**
- ✅ Uses existing dashboard data
- ✅ No extra API calls

**Cons:**
- ❌ Complex parsing
- ❌ May not have all values if queries are filtered

## Immediate Fix: Enhanced Logging

Added logging to help diagnose:

```python
logger.warning(
    "No values found for template variable in host tags",
    variable=name,
    prefix=prefix,
    is_likely_metric_tag=True,  # Detects "table", "metric", etc.
    hint="Use available_values or metric tag APIs"
)
```

## How to Check Current Status

1. **Extract metrics** for the dashboard
2. **Check logs** for warnings about metric tags
3. **View template variables** in the UI - will show "no values resolved"

## Next Steps

1. ✅ **Done**: Enhanced logging for metric tag detection
2. 🔄 **In Progress**: Check if dashboard has `available_values` defined
3. 📋 **TODO**: Implement metric tag value extraction (Solution 2 or 3)

## Testing

To test with the DynamoDB dashboard:

1. Extract metrics: `POST /api/v1/dashboards/{id}/extract-metrics`
2. Check logs for: `"No values found for template variable in host tags"`
3. View variables: `GET /api/v1/organizations/{org_id}/template-variables?dashboard_id={id}`
4. Should see `tablename` with empty `values: []`

## Related Code

- `app/adapters/datadog/adapter.py:606` - `resolve_template_variables()`
- `app/adapters/datadog/client.py:230` - `list_host_tags()`
- `app/services/metric_extract_service.py:78` - Template variable extraction
