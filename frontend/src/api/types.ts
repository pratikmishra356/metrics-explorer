export type ProviderType = 'datadog' | 'prometheus' | 'grafana'

export interface Organization {
  id: string
  name: string
  slug: string
  description?: string
  metadata: Record<string, unknown>
  used_dashboards?: string[]
  providers: OrganizationProvider[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface OrganizationProvider {
  id: string
  organization_id: string
  provider_type: ProviderType
  name: string
  description?: string
  endpoint_url?: string
  config: ProviderConfig
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProviderConfig {
  timeout_seconds?: number
  max_retries?: number
  rate_limit_requests?: number
  custom_settings?: Record<string, unknown>
}

export interface CreateOrganizationRequest {
  name: string
  slug: string
  description?: string
  metadata?: Record<string, unknown>
}

export interface CreateProviderRequest {
  provider_type: ProviderType
  name: string
  description?: string
  endpoint_url?: string
  credentials: Record<string, string>
  config?: ProviderConfig
}

export interface DashboardSummary {
  id: string
  title: string
  description?: string
  tags: string[]
  folder?: string
  widget_count: number
  created_at?: string
  modified_at?: string
  url?: string
  provider_source: string
}

export interface DashboardListResponse {
  dashboards: DashboardSummary[]
  total_count: number
  providers_queried: string[]
}

export interface MonitorSummary {
  id: string
  name: string
  description?: string
  monitor_type: string
  status: string
  priority?: string
  tags: string[]
  is_muted: boolean
  last_triggered_at?: string
  url?: string
  provider_source: string
}

export interface MonitorListResponse {
  monitors: MonitorSummary[]
  total_count: number
  providers_queried: string[]
  status_counts: Record<string, number>
}

export interface MetricQueryRequest {
  metric_names?: string[]
  metric_name_pattern?: string
  start_time: string
  end_time: string
  attribute_filters?: Record<string, unknown>
  resource_filters?: Record<string, unknown>
  aggregation?: string
  group_by?: string[]
  step_seconds?: number
  limit?: number
}

export interface ProvidersResponse {
  providers: string[]
  count: number
}

/* ---- Dashboard Metric Query ---- */

export interface DashboardQueryMetricItem {
  metric_name: string
  aggregation?: string
  filters?: Record<string, string | string[]>
  group_by?: string[]
  limit?: number
}

export interface DashboardQueryTimeRange {
  start?: number
  end?: number
  relative?: string
}

export interface DashboardQueryRequest {
  queries: DashboardQueryMetricItem[]
  time_range?: DashboardQueryTimeRange
}

export interface QueryDataPoint {
  timestamp: number
  value: number | null
}

export interface QuerySeries {
  scope: string
  tags: Record<string, string>
  datapoints: QueryDataPoint[]
  unit?: string
}

export interface QueryResultItem {
  query_index: number
  metric_name: string
  display_name?: string
  expression?: string
  series: QuerySeries[]
  series_count: number
  datapoint_count: number
  query_time_ms: number
  error?: string
}

export interface DashboardQueryResponse {
  dashboard_id: string
  provider: string
  results: QueryResultItem[]
  total_queries: number
  total_series: number
  total_datapoints: number
  execution_time_ms: number
}

export interface MetricMetadataListResponse {
  metrics: Array<{
    name: string
    description?: string
    unit?: string
    metric_type: string
    available_attributes: string[]
    provider_source: string
    help_text?: string
  }>
  total_count: number
  providers_queried: string[]
}
