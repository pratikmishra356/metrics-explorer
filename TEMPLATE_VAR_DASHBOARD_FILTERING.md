# How Dashboard-Specific Template Variable Filtering Works

## The Key Insight

**`/api/v1/tags/hosts` returns ALL tags (account-wide), but we only resolve variables that are DEFINED on the specific dashboard.**

## Example Scenario

### Datadog Account Has These Host Tags:
```
env:production
env:staging
env:dev
service:web
service:api
service:worker
region:us-east-1
region:us-west-2
region:eu-west-1
```

### Dashboard A Template Variables:
```json
[
  {"name": "env", "prefix": "env", "default": "*"},
  {"name": "service", "prefix": "service", "default": "*"}
]
```

### Dashboard B Template Variables:
```json
[
  {"name": "region", "prefix": "region", "default": "*"},
  {"name": "env", "prefix": "env", "default": "*"}
]
```

## Flow for Dashboard A

```
1. Fetch Dashboard A detail
   → dashboard.provider_metadata.template_variables = [
       {name: "env", prefix: "env"},
       {name: "service", prefix: "service"}
     ]

2. Call resolve_template_variables(template_variables=[...])
   → Passes ONLY Dashboard A's variables

3. Fetch ALL host tags (account-wide)
   → GET /api/v1/tags/hosts
   → Returns: {"env:production": [...], "env:staging": [...], 
               "service:web": [...], "region:us-east-1": [...], ...}

4. Build structured map (account-wide)
   → {
       "env": ["production", "staging", "dev"],
       "service": ["web", "api", "worker"],
       "region": ["us-east-1", "us-west-2", "eu-west-1"]
     }

5. Filter by Dashboard A's variables ONLY
   → Loop through: ["env", "service"]  ← Only these!
   → resolved["env"] = structured.get("env") = ["production", "staging", "dev"]
   → resolved["service"] = structured.get("service") = ["web", "api", "worker"]
   → SKIP "region" (not in Dashboard A's variables)

6. Store in DB with dashboard_id = Dashboard A's ID
   → template_variables table:
     - (org_id, dashboard_A_id, "env", ...)
     - (org_id, dashboard_A_id, "service", ...)
```

## Flow for Dashboard B

```
1. Fetch Dashboard B detail
   → dashboard.provider_metadata.template_variables = [
       {name: "region", prefix: "region"},
       {name: "env", prefix: "env"}
     ]

2. Call resolve_template_variables(template_variables=[...])
   → Passes ONLY Dashboard B's variables

3. Fetch ALL host tags (account-wide) - SAME CALL
   → GET /api/v1/tags/hosts
   → Returns: Same account-wide tags

4. Build structured map (account-wide) - SAME MAP
   → Same as Dashboard A

5. Filter by Dashboard B's variables ONLY
   → Loop through: ["region", "env"]  ← Only these!
   → resolved["region"] = structured.get("region") = ["us-east-1", "us-west-2", "eu-west-1"]
   → resolved["env"] = structured.get("env") = ["production", "staging", "dev"]
   → SKIP "service" (not in Dashboard B's variables)

6. Store in DB with dashboard_id = Dashboard B's ID
   → template_variables table:
     - (org_id, dashboard_B_id, "region", ...)
     - (org_id, dashboard_B_id, "env", ...)
```

## Code Flow

### Step 1: Dashboard-Specific Variables Extracted
```python
# metric_extract_service.py, line 80
raw_template_vars = dashboard.provider_metadata.get("template_variables", [])
# ↑ This comes from THIS specific dashboard's JSON
```

### Step 2: Only These Variables Are Resolved
```python
# metric_extract_service.py, line 83-87
resolved_vars = await self.query_service.resolve_template_variables(
    template_variables=raw_template_vars,  # ← Dashboard-specific list
)
```

### Step 3: Resolver Filters Host Tags
```python
# datadog/adapter.py, line 653-667
for var in template_variables:  # ← Only loops through passed variables
    prefix = var.get("prefix")  # e.g., "env" or "service"
    # Only look up THIS prefix in the host tags
    values = sorted(structured.get(prefix, set()))
    # ↑ Filters the account-wide tags by this dashboard's prefix
```

### Step 4: Stored with Dashboard ID
```python
# metric_extract_service.py, line 117-125
await self.template_var_repo.upsert(
    dashboard_id=db_dashboard.id,  # ← Links to THIS dashboard
    variable_name=var_name,
    ...
)
```

## Why This Works

1. **Each dashboard defines its own variables** in its JSON metadata
2. **We only pass those variables** to the resolver
3. **The resolver filters** the account-wide host tags by matching prefixes
4. **Storage links variables** to the specific dashboard via `dashboard_id`

## Database Uniqueness

The `template_variables` table has a unique constraint:
```sql
UNIQUE(organization_id, dashboard_id, variable_name)
```

This ensures:
- Same variable name can exist on different dashboards
- Each dashboard's variables are stored separately
- No conflicts between dashboards

## Summary

✅ `/api/v1/tags/hosts` returns **ALL** tags (account-wide)  
✅ But we only resolve variables **defined on the specific dashboard**  
✅ Filtering happens by matching `variable.prefix` → `tag_key`  
✅ Storage links variables to dashboard via `dashboard_id`  
✅ Each dashboard's variables are stored separately in the DB
