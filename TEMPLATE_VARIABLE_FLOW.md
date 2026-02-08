# Template Variable Flow

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER ACTION: "Extract Metrics"                               │
│    → MetricExtractService.extract_metrics()                     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. FETCH DASHBOARD DETAIL                                       │
│    → query_service.get_dashboard()                               │
│    → DatadogAdapter.get_dashboard()                             │
│    → GET /api/v1/dashboard/{id}                                 │
│                                                                  │
│    📦 Dashboard object includes:                                │
│       - provider_metadata.template_variables = [                │
│           {name: "env", prefix: "env", default: "*"},           │
│           {name: "service", prefix: "service", default: "*"}    │
│         ]                                                        │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. RESOLVE TEMPLATE VARIABLES                                   │
│    → query_service.resolve_template_variables()                 │
│    → DatadogAdapter.resolve_template_variables()                 │
│    → GET /api/v1/tags/hosts  (ONE API CALL)                     │
│                                                                  │
│    🔍 Resolution logic:                                         │
│       - Parse tag_kv pairs: "env:prod", "env:staging"           │
│       - Build map: {"env": ["prod", "staging"], ...}            │
│       - Match variable.prefix → tag_key                          │
│                                                                  │
│    ✅ Returns:                                                   │
│       {                                                          │
│         "env": {                                                │
│           name: "env",                                          │
│           tag_key: "env",                                       │
│           default: "*",                                          │
│           values: ["prod", "staging", "dev"]                     │
│         },                                                       │
│         "service": {...}                                         │
│       }                                                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. STORE IN template_variables TABLE                            │
│    → TemplateVariableRepository.upsert()                        │
│                                                                  │
│    📊 For each resolved variable:                               │
│       - Check cardinality: len(values) > 5000?                  │
│         → YES: Skip (log warning)                                │
│         → NO: Upsert to DB                                       │
│                                                                  │
│    💾 Stored in: template_variables table                        │
│       - organization_id                                         │
│       - dashboard_id (DB FK)                                    │
│       - variable_name (unique per org+dash+name)                │
│       - tag_key                                                  │
│       - default_value                                            │
│       - values (JSON array)                                      │
│       - provider                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. EXTRACT WIDGETS & STORE METRICS                              │
│    → _extract_widget_items()                                    │
│                                                                  │
│    For each widget:                                             │
│       - Scan queries for $var_name patterns                      │
│       - Find used variables: ["env", "service"]                 │
│       - Store in metric.details:                                │
│         {                                                        │
│           template_variable_names: ["env", "service"],          │
│           requests: [...],                                       │
│           ...                                                    │
│         }                                                        │
│                                                                  │
│    💾 Stored in: dashboard_metrics table                        │
│       - Only variable NAMES (not full objects)                   │
│       - Full values live in template_variables table             │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. COMMIT TRANSACTION                                           │
│    → session.commit()                                            │
│                                                                  │
│    ✅ Result summary:                                            │
│       {                                                          │
│         created: 10,                                             │
│         updated: 5,                                              │
│         template_variables_stored: 3,                            │
│         template_variables_skipped_high_cardinality: 1           │
│       }                                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Key Points

### When Template Variables Are Stored

**Storage happens ONLY during "Extract Metrics" action**, NOT during:
- ❌ Dashboard sync (only stores dashboard metadata)
- ❌ Dashboard listing (only fetches summaries)

### Storage Locations

1. **`template_variables` table** (Primary storage)
   - Full resolved variable definitions with values
   - One row per `(org_id, dashboard_id, variable_name)`
   - Accessed via: `GET /api/v1/organizations/{org_id}/template-variables`

2. **`dashboard_metrics.details.template_variable_names`** (Reference only)
   - Just the variable names used by each widget
   - Lightweight JSON array: `["env", "service"]`
   - Used for quick reference in metric cards

### High Cardinality Protection

Variables with >5,000 resolved values are **skipped** to prevent:
- Database bloat
- Performance issues
- Rate limit exhaustion

### API Calls Made

- **ONE** call per extraction: `GET /api/v1/tags/hosts`
- All variables resolved from this single response
- No per-variable API calls

### Frontend Display

- **Per-dashboard**: Click "View Variables" → loads from `template_variables` table
- **Per-metric**: Shows variable name chips in expanded metric card
- **No auto-fetch**: All data loads require explicit user action
