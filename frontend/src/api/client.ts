import type {
  Organization,
  OrganizationProvider,
  CreateProviderRequest,
  DashboardListResponse,
  MonitorListResponse,
  MetricQueryRequest,
  MetricMetadataListResponse,
  ProvidersResponse,
  DashboardQueryRequest,
  DashboardQueryResponse,
} from './types'

const getBaseUrl = () => {
  const v = import.meta.env.VITE_API_BASE_URL
  if (v) return v.replace(/\/$/, '')
  return ''
}

function headers(orgId: string | null): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (orgId) h['X-Organization-Id'] = orgId
  return h
}

async function request<T>(
  path: string,
  options: RequestInit & { orgId?: string | null } = {}
): Promise<{ data: T; status: number }> {
  const { orgId, ...init } = options
  const base = getBaseUrl()
  const url = base ? `${base}${path}` : path
  const res = await fetch(url, {
    ...init,
    headers: { ...headers(orgId ?? null), ...(init.headers as Record<string, string>) },
  })
  const text = await res.text()
  let data: T
  try {
    data = text ? (JSON.parse(text) as T) : ({} as T)
  } catch {
    throw new Error(text || res.statusText)
  }
  if (!res.ok) throw new Error((data as { message?: string }).message || res.statusText)
  return { data, status: res.status }
}

export const api = {
  // Organizations
  listOrganizations(params?: { limit?: number; offset?: number }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<Organization[]>(`/api/v1/organizations${q ? `?${q}` : ''}`)
  },
  createOrganization(body: { name: string; slug: string; description?: string; metadata?: Record<string, unknown> }) {
    return request<Organization>('/api/v1/organizations', { method: 'POST', body: JSON.stringify(body) })
  },
  getOrganization(orgId: string) {
    return request<Organization>(`/api/v1/organizations/${orgId}`)
  },
  listOrganizationProviders(orgId: string) {
    return request<OrganizationProvider[]>(`/api/v1/organizations/${orgId}/providers`)
  },
  addProvider(orgId: string, body: CreateProviderRequest) {
    return request<OrganizationProvider>(`/api/v1/organizations/${orgId}/providers`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
  removeProvider(orgId: string, providerId: string) {
    return request(`/api/v1/organizations/${orgId}/providers/${providerId}`, { method: 'DELETE' })
  },

  // Dashboards
  listDashboards(orgId: string, params?: { tags?: string; folder?: string; provider?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<DashboardListResponse>(`/api/v1/dashboards${q ? `?${q}` : ''}`, { orgId })
  },
  getDashboard(orgId: string, dashboardId: string, provider?: string) {
    const q = provider ? `?provider=${provider}` : ''
    return request<unknown>(`/api/v1/dashboards/${encodeURIComponent(dashboardId)}${q}`, { orgId })
  },
  syncDashboards(orgId: string, provider?: string) {
    const q = provider ? `?provider=${provider}` : ''
    return request<{ status: string; message: string; created: number; updated: number; skipped: number; total_fetched: number }>(`/api/v1/dashboards/sync${q}`, { method: 'POST', orgId })
  },
  listStoredDashboards(orgId: string, params?: { provider?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<{ dashboards: Array<{ id: string; dashboard_id: string; title: string; description: string | null; provider_type: string; provider_source: string | null; metadata: Record<string, unknown>; created_at: string | null; updated_at: string | null }>; total_count: number }>(`/api/v1/dashboards/stored${q ? `?${q}` : ''}`, { orgId })
  },
  extractMetrics(orgId: string, dashboardId: string, provider?: string) {
    const q = provider ? `?provider=${provider}` : ''
    return request<{ status: string; message: string; created: number; updated: number; total: number; dashboard_id: string; provider_dashboard_id: string }>(`/api/v1/dashboards/${encodeURIComponent(dashboardId)}/extract-metrics${q}`, { method: 'POST', orgId })
  },
  listDashboardMetrics(orgId: string, dashboardDbId: string, params?: { provider?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<{ metrics: Array<{ id: string; dashboard_id: string; provider: string; widget_id: string | null; name: string | null; description: string | null; details: Record<string, unknown>; created_at: string | null; updated_at: string | null }>; total_count: number }>(`/api/v1/dashboards/${encodeURIComponent(dashboardDbId)}/metrics${q ? `?${q}` : ''}`, { orgId })
  },

  // Monitors
  listMonitors(orgId: string, params?: { tags?: string; status?: string; provider?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<MonitorListResponse>(`/api/v1/monitors${q ? `?${q}` : ''}`, { orgId })
  },
  getMonitor(orgId: string, monitorId: string, provider?: string) {
    const q = provider ? `?provider=${provider}` : ''
    return request<unknown>(`/api/v1/monitors/${encodeURIComponent(monitorId)}${q}`, { orgId })
  },

  // Metrics
  queryMetrics(orgId: string, body: MetricQueryRequest) {
    return request<unknown>('/api/v1/metrics/query', { method: 'POST', body: JSON.stringify(body), orgId })
  },
  getMetricsMetadata(orgId: string, params?: { metric_names?: string; provider?: string; limit?: number }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<MetricMetadataListResponse>(`/api/v1/metrics/metadata${q ? `?${q}` : ''}`, { orgId })
  },
  listProviders(orgId: string) {
    return request<ProvidersResponse>('/api/v1/metrics/providers', { orgId })
  },

  // Dashboard Metric Querying
  queryDashboardMetrics(orgId: string, dashboardId: string, body: DashboardQueryRequest, provider?: string) {
    const q = provider ? `?provider=${provider}` : ''
    return request<DashboardQueryResponse>(
      `/api/v1/dashboards/${encodeURIComponent(dashboardId)}/query${q}`,
      { method: 'POST', body: JSON.stringify(body), orgId }
    )
  },

  // Template Variables
  listTemplateVariables(orgId: string, params?: { dashboard_id?: string; provider?: string }) {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<{
      template_variables: Array<{
        id: string
        organization_id: string
        dashboard_id: string
        variable_name: string
        tag_key: string
        default_value: string | null
        values: string[]
        provider: string
        created_at: string
        updated_at: string
      }>
      total_count: number
    }>(`/api/v1/organizations/${encodeURIComponent(orgId)}/template-variables${q ? `?${q}` : ''}`)
  },

  // Used Dashboards
  getUsedDashboards(orgId: string) {
    return request<{
      dashboard_ids: string[]
      used_dashboards: Array<{ id: string; dashboard_id: string; title: string; description: string | null; provider_type: string }>
      total_count: number
    }>(`/api/v1/organizations/${encodeURIComponent(orgId)}/used-dashboards`)
  },
  setUsedDashboards(orgId: string, dashboardIds: string[]) {
    return request<{ status: string; used_dashboards: string[]; total_count: number }>(
      `/api/v1/organizations/${encodeURIComponent(orgId)}/used-dashboards`,
      { method: 'PUT', body: JSON.stringify({ dashboard_ids: dashboardIds }) }
    )
  },

  // Search
  searchDashboards(orgId: string, search?: string, params?: { provider?: string; limit?: number }) {
    const p = new URLSearchParams()
    if (search) p.set('search', search)
    if (params?.provider) p.set('provider', params.provider)
    if (params?.limit) p.set('limit', params.limit.toString())
    return request<{
      dashboards: Array<{ id: string; dashboard_id: string; title: string; description: string | null; provider_type: string; provider_source: string | null }>
      total_count: number
      search: string | null
    }>(`/api/v1/organizations/${encodeURIComponent(orgId)}/dashboards/search${p.toString() ? `?${p.toString()}` : ''}`)
  },
  searchDashboardMetrics(orgId: string, dashboardDbId: string, search?: string, params?: { provider?: string; limit?: number }) {
    const p = new URLSearchParams()
    if (search) p.set('search', search)
    if (params?.provider) p.set('provider', params.provider)
    if (params?.limit) p.set('limit', params.limit.toString())
    return request<{
      metrics: Array<{ id: string; widget_id: string | null; name: string | null; description: string | null; provider: string; details: Record<string, unknown> }>
      total_count: number
      search: string | null
    }>(`/api/v1/organizations/${encodeURIComponent(orgId)}/dashboards/${encodeURIComponent(dashboardDbId)}/metrics/search${p.toString() ? `?${p.toString()}` : ''}`)
  },
  getVariableValues(orgId: string, dashboardDbId: string, variableName: string, search?: string) {
    const p = new URLSearchParams()
    if (search) p.set('search', search)
    const q = p.toString()
    return request<{
      variable_name: string
      tag_key: string
      default_value: string | null
      values: string[]
      total_count: number
      returned_count: number
    }>(`/api/v1/organizations/${encodeURIComponent(orgId)}/dashboards/${encodeURIComponent(dashboardDbId)}/variables/${encodeURIComponent(variableName)}/values${q ? `?${q}` : ''}`)
  },
}
