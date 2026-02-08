import { useState, useMemo } from 'react'
import { api } from '../api/client'
import { ResponseViewer } from './ResponseViewer'
import { ProviderBadge } from './ProviderBadge'
import { MetricQueryPanel } from './MetricQueryPanel'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface StoredDashboard {
  id: string
  dashboard_id: string
  title: string
  description: string | null
  provider_type: string
  provider_source: string | null
  metadata: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
}

interface DashboardMetric {
  id: string
  dashboard_id: string
  provider: string
  widget_id: string | null
  name: string | null
  description: string | null
  details: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
}

interface DashboardsProps {
  orgId: string
  providerFilter: string
}

/* ------------------------------------------------------------------ */
/*  Provider color map                                                 */
/* ------------------------------------------------------------------ */

const PROVIDER_COLORS: Record<string, { bg: string; text: string; border: string; accent: string }> = {
  datadog: { bg: '#f5f0ff', text: '#6b21a8', border: '#d8b4fe', accent: '#7c3aed' },
  prometheus: { bg: '#fef2f2', text: '#991b1b', border: '#fca5a5', accent: '#dc2626' },
  grafana: { bg: '#fefce8', text: '#854d0e', border: '#fde047', accent: '#ca8a04' },
}

const DEFAULT_PROVIDER_COLOR = { bg: '#f8fafc', text: '#475569', border: '#cbd5e1', accent: '#64748b' }

function getProviderColor(provider: string) {
  return PROVIDER_COLORS[provider.toLowerCase()] || DEFAULT_PROVIDER_COLOR
}

/* ------------------------------------------------------------------ */
/*  JSON Viewer                                                        */
/* ------------------------------------------------------------------ */

function JsonViewer({ data, collapsed = true }: { data: unknown; collapsed?: boolean }) {
  const [open, setOpen] = useState(!collapsed)
  const json = typeof data === 'string' ? data : JSON.stringify(data, null, 2)

  return (
    <div className="json-viewer">
      <button
        className="json-toggle"
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        {open ? 'Collapse JSON' : 'Expand JSON'}
      </button>
      {open && <pre className="json-content">{json}</pre>}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Metric Card                                                        */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Template Variable Types (from DB table)                             */
/* ------------------------------------------------------------------ */

interface TemplateVariableEntry {
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
}

/* ------------------------------------------------------------------ */
/*  Template Variables Viewer (per-dashboard, from dedicated table)     */
/* ------------------------------------------------------------------ */

function TemplateVariablesPanel({ variables }: { variables: TemplateVariableEntry[] }) {
  const [expandedVars, setExpandedVars] = useState<Set<string>>(new Set())

  if (variables.length === 0) return null

  const toggleVar = (name: string) => {
    setExpandedVars((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  return (
    <div className="template-vars-section">
      <div className="template-vars-section__header">
        Template Variables
        <span className="template-vars-section__count">{variables.length}</span>
      </div>
      <div className="template-vars-section__list">
        {variables.map((v) => {
          const isExpanded = expandedVars.has(v.variable_name)
          const hasValues = v.values && v.values.length > 0
          return (
            <div key={v.id} className="template-var-card">
              <div
                className="template-var-card__header"
                onClick={() => hasValues && toggleVar(v.variable_name)}
                style={{ cursor: hasValues ? 'pointer' : 'default' }}
              >
                <code className="template-var-card__name">${v.variable_name}</code>
                <span className="template-var-card__key">{v.tag_key}</span>
                {v.default_value && v.default_value !== '*' && (
                  <span className="template-var-card__default">
                    default: {v.default_value}
                  </span>
                )}
                {hasValues && (
                  <span className="template-var-card__value-count">
                    {isExpanded ? '\u25BC' : '\u25B6'} {v.values.length} values
                  </span>
                )}
                {!hasValues && (
                  <span className="template-var-card__no-values">no values resolved</span>
                )}
              </div>
              {isExpanded && hasValues && (
                <div className="template-var-card__values">
                  {v.values.map((val) => (
                    <span key={val} className="template-var-card__value-chip">
                      {val}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Metric Card                                                        */
/* ------------------------------------------------------------------ */

function MetricCard({ metric }: { metric: DashboardMetric }) {
  const [expanded, setExpanded] = useState(false)
  const details = metric.details || {}
  const parentGroup = details.parent_group_details as Record<string, unknown> | undefined
  const requests = (details.requests || []) as Array<Record<string, unknown>>
  const templateVarNames = (details.template_variable_names || []) as string[]
  const widgetType = (details.widget_type as string) || ''
  const widgetTitle = (details.widget_title as string) || ''
  const providerColor = getProviderColor(metric.provider)

  const totalQueries = requests.reduce(
    (sum, r) => sum + ((r.queries as unknown[]) || []).length,
    0
  )

  return (
    <div
      className="metric-card"
      style={{ borderLeftColor: providerColor.accent }}
    >
      {/* Header */}
      <div className="metric-card__header" onClick={() => setExpanded((v) => !v)}>
        <div className="metric-card__title-row">
          <span className="metric-card__expand">{expanded ? '\u25BC' : '\u25B6'}</span>
          <h4 className="metric-card__title">{metric.name || widgetTitle || '(unnamed)'}</h4>
          <ProviderBadge provider={metric.provider} />
          {widgetType && (
            <span className="metric-card__type-badge">{widgetType}</span>
          )}
          {templateVarNames.length > 0 && (
            <span className="metric-card__vars-badge">
              {templateVarNames.length} var{templateVarNames.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="metric-card__subtitle">
          {metric.description && <span>{metric.description}</span>}
          {!metric.description && totalQueries > 0 && (
            <span>{totalQueries} quer{totalQueries === 1 ? 'y' : 'ies'}</span>
          )}
          <span className="metric-card__widget-id">Widget: {metric.widget_id || 'N/A'}</span>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="metric-card__body">
          {/* Template variable names as simple chips */}
          {templateVarNames.length > 0 && (
            <div className="metric-card__var-chips">
              <span className="metric-card__var-chips-label">Variables:</span>
              {templateVarNames.map((v) => (
                <span key={v} className="metric-card__var-chip">${v}</span>
              ))}
            </div>
          )}

          {/* Parent group */}
          {parentGroup && (
            <div className="metric-card__group-banner">
              <strong>Parent Group:</strong> {(parentGroup.group_title as string) || 'N/A'}
              {parentGroup.group_layout_type ? (
                <span className="metric-card__group-layout">
                  ({String(parentGroup.group_layout_type)})
                </span>
              ) : null}
            </div>
          )}

          {/* Requests / Queries section */}
          {requests.length > 0 && (
            <div className="metric-card__requests">
              {requests.map((req, ri) => {
                const queries = (req.queries || []) as Array<Record<string, unknown>>
                const formulas = (req.formulas || []) as Array<Record<string, unknown>>
                const displayType = (req.display_type as string) || ''
                const responseFormat = (req.response_format as string) || ''

                return (
                  <div key={ri} className="metric-card__request">
                    {requests.length > 1 && (
                      <div className="metric-card__request-label">
                        Request {ri + 1}
                        {displayType && <span className="metric-card__display-type">{displayType}</span>}
                        {responseFormat && <span className="metric-card__response-fmt">{responseFormat}</span>}
                      </div>
                    )}

                    {/* Queries */}
                    {queries.map((q, qi) => (
                      <div key={qi} className="metric-card__query">
                        <div className="metric-card__query-header">
                          <span className="metric-card__query-name">
                            {(q.name as string) || `query${qi}`}
                          </span>
                          {q.data_source ? (
                            <span className="metric-card__query-source">
                              {String(q.data_source)}
                            </span>
                          ) : null}
                        </div>
                        <code className="metric-card__query-string">
                          {(q.query as string) || 'N/A'}
                        </code>
                      </div>
                    ))}

                    {/* Formulas */}
                    {formulas.length > 0 && (
                      <div className="metric-card__formulas">
                        <span className="metric-card__formulas-label">Formulas:</span>
                        {formulas.map((f, fi) => (
                          <span key={fi} className="metric-card__formula">
                            {(f.alias as string)
                              ? `${f.alias} = ${f.formula}`
                              : (f.formula as string) || ''}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Full details JSON */}
          <JsonViewer data={details} collapsed />
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Dashboards Component                                          */
/* ------------------------------------------------------------------ */

export function Dashboards({ orgId, providerFilter }: DashboardsProps) {
  const [dashboardId, setDashboardId] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [extracting, setExtracting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<unknown>(null)
  const [storedDashboards, setStoredDashboards] = useState<StoredDashboard[]>([])
  const [selectedDashMetrics, setSelectedDashMetrics] = useState<DashboardMetric[]>([])
  const [selectedDashId, setSelectedDashId] = useState<string | null>(null)
  const [dashboardSearch, setDashboardSearch] = useState('')
  const [status, setStatus] = useState('')
  // Template variables per dashboard (keyed by dashboard DB id)
  const [dashTemplateVars, setDashTemplateVars] = useState<Record<string, TemplateVariableEntry[]>>({})
  const [loadingVarsDash, setLoadingVarsDash] = useState<string | null>(null)
  // Query panel (keyed by dashboard DB id)
  const [queryPanelDashId, setQueryPanelDashId] = useState<string | null>(null)
  const [queryPanelMetrics, setQueryPanelMetrics] = useState<DashboardMetric[]>([])
  const [queryPanelVars, setQueryPanelVars] = useState<TemplateVariableEntry[]>([])
  const [loadingQueryPanel, setLoadingQueryPanel] = useState<string | null>(null)
  // Used dashboards
  const [usedDashboardIds, setUsedDashboardIds] = useState<Set<string>>(new Set())
  const [savingUsed, setSavingUsed] = useState(false)
  // Server-side search
  const [serverSearch, setServerSearch] = useState('')
  const [serverSearchResults, setServerSearchResults] = useState<StoredDashboard[] | null>(null)
  const [searching, setSearching] = useState(false)

  /* ---- API actions ---- */

  const listDashboards = async () => {
    if (!orgId.trim()) return
    setLoading(true); setError(null); setResponse(null)
    try {
      const params: Record<string, string> = {}
      if (providerFilter) params.provider = providerFilter
      const { data, status: s } = await api.listDashboards(orgId.trim(), params as { provider?: string })
      setResponse(data); setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setStatus('Error')
    } finally { setLoading(false) }
  }

  const getDashboard = async () => {
    if (!orgId.trim() || !dashboardId.trim()) return
    setLoading(true); setError(null); setResponse(null)
    try {
      const { data, status: s } = await api.getDashboard(orgId.trim(), dashboardId.trim(), providerFilter || undefined)
      setResponse(data); setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setStatus('Error')
    } finally { setLoading(false) }
  }

  const syncDashboards = async () => {
    if (!orgId.trim()) return
    setSyncing(true); setError(null); setResponse(null)
    try {
      const params: Record<string, string> = {}
      if (providerFilter) params.provider = providerFilter
      const { data, status: s } = await api.syncDashboards(orgId.trim(), params.provider)
      setResponse(data); setStatus(`${s}`)
      await loadStoredDashboards()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setStatus('Error')
    } finally { setSyncing(false) }
  }

  const loadStoredDashboards = async () => {
    if (!orgId.trim()) return
    try {
      const params: Record<string, string> = { limit: '2000' }
      if (providerFilter) params.provider = providerFilter
      const { data } = await api.listStoredDashboards(orgId.trim(), params as { provider?: string; limit?: number })
      setStoredDashboards(data.dashboards)
    } catch (e) {
      console.error('Failed to load stored dashboards:', e)
    }
  }

  const extractMetrics = async (providerDashboardId: string) => {
    if (!orgId.trim()) return
    setExtracting(providerDashboardId); setError(null)
    try {
      const { data, status: s } = await api.extractMetrics(orgId.trim(), providerDashboardId, providerFilter || undefined)
      setResponse(data); setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setStatus('Error')
    } finally { setExtracting(null) }
  }

  const viewMetrics = async (dashDbId: string) => {
    if (!orgId.trim()) return
    if (selectedDashId === dashDbId) {
      setSelectedDashId(null); setSelectedDashMetrics([]); return
    }
    try {
      const { data } = await api.listDashboardMetrics(orgId.trim(), dashDbId)
      setSelectedDashMetrics(data.metrics); setSelectedDashId(dashDbId)
    } catch (e) {
      console.error('Failed to load metrics:', e)
      setSelectedDashMetrics([]); setSelectedDashId(null)
    }
  }

  const loadTemplateVars = async (dashDbId: string) => {
    if (!orgId.trim()) return
    // Toggle off
    if (dashTemplateVars[dashDbId]) {
      setDashTemplateVars((prev) => {
        const next = { ...prev }
        delete next[dashDbId]
        return next
      })
      return
    }
    setLoadingVarsDash(dashDbId)
    try {
      const { data } = await api.listTemplateVariables(orgId.trim(), { dashboard_id: dashDbId })
      setDashTemplateVars((prev) => ({ ...prev, [dashDbId]: data.template_variables }))
    } catch (e) {
      console.error('Failed to load template variables:', e)
    } finally {
      setLoadingVarsDash(null)
    }
  }

  const openQueryPanel = async (dash: StoredDashboard) => {
    // Toggle off
    if (queryPanelDashId === dash.id) {
      setQueryPanelDashId(null)
      setQueryPanelMetrics([])
      setQueryPanelVars([])
      return
    }
    setLoadingQueryPanel(dash.id)
    try {
      // Load extracted metrics + template variables in parallel
      const [metricsRes, varsRes] = await Promise.all([
        api.listDashboardMetrics(orgId.trim(), dash.id),
        api.listTemplateVariables(orgId.trim(), { dashboard_id: dash.id }),
      ])
      setQueryPanelMetrics(metricsRes.data.metrics)
      setQueryPanelVars(varsRes.data.template_variables)
      setQueryPanelDashId(dash.id)
    } catch (e) {
      console.error('Failed to open query panel:', e)
    } finally {
      setLoadingQueryPanel(null)
    }
  }

  /* ---- Used dashboards ---- */

  const loadUsedDashboards = async () => {
    if (!orgId.trim()) return
    try {
      const { data } = await api.getUsedDashboards(orgId.trim())
      setUsedDashboardIds(new Set(data.dashboard_ids || []))
    } catch (e) {
      console.error('Failed to load used dashboards:', e)
    }
  }

  const toggleUsedDashboard = async (providerDashId: string) => {
    const next = new Set(usedDashboardIds)
    if (next.has(providerDashId)) next.delete(providerDashId)
    else next.add(providerDashId)
    setUsedDashboardIds(next)
    setSavingUsed(true)
    try {
      await api.setUsedDashboards(orgId.trim(), Array.from(next))
    } catch (e) {
      console.error('Failed to save used dashboards:', e)
    } finally {
      setSavingUsed(false)
    }
  }

  /* ---- Server-side search ---- */

  const runServerSearch = async () => {
    if (!orgId.trim()) return
    setSearching(true)
    try {
      const { data } = await api.searchDashboards(
        orgId.trim(),
        serverSearch.trim() || undefined, // Pass undefined if empty to get all
        {
          provider: providerFilter || undefined,
          limit: 100,
        } as { provider?: string; limit?: number }
      )
      setServerSearchResults(data.dashboards as StoredDashboard[])
    } catch (e) {
      console.error('Server search failed:', e)
      setServerSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const clearServerSearch = () => {
    setServerSearch('')
    setServerSearchResults(null)
  }

  /* ---- Group dashboards by provider ---- */

  // Use server search results if available, otherwise local filter
  const displayDashboards = serverSearchResults ?? storedDashboards

  const groupedDashboards = useMemo(() => {
    const filtered = dashboardSearch.trim() && !serverSearchResults
      ? displayDashboards.filter(
          (d) =>
            d.title.toLowerCase().includes(dashboardSearch.toLowerCase()) ||
            d.dashboard_id.toLowerCase().includes(dashboardSearch.toLowerCase())
        )
      : displayDashboards

    const groups: Record<string, StoredDashboard[]> = {}
    for (const d of filtered) {
      const key = d.provider_type || 'unknown'
      if (!groups[key]) groups[key] = []
      groups[key].push(d)
    }
    return groups
  }, [storedDashboards, dashboardSearch])

  const providerKeys = Object.keys(groupedDashboards).sort()

  /* ---- Render ---- */

  return (
    <div>
      {/* Top controls */}
      <section className="card">
        <h2>Dashboards</h2>
        <div className="form-row">
          <button onClick={async () => { await loadStoredDashboards(); await loadUsedDashboards() }} disabled={loading || !orgId.trim()}>
            Load Stored Dashboards
          </button>
          <button onClick={syncDashboards} disabled={syncing || !orgId.trim()}>
            {syncing ? 'Syncing...' : 'Sync from Providers'}
          </button>
          <button onClick={listDashboards} disabled={loading || !orgId.trim()}>
            List from Providers
          </button>
        </div>
        <div className="form-row" style={{ marginTop: '0.5rem' }}>
          <input placeholder="Dashboard ID" value={dashboardId} onChange={(e) => setDashboardId(e.target.value)} />
          <button onClick={getDashboard} disabled={loading || !orgId.trim() || !dashboardId.trim()}>
            Get Dashboard Detail
          </button>
        </div>
        <ResponseViewer data={response} status={status} error={error} loading={loading || syncing} />
      </section>

      {/* Used dashboards summary */}
      {usedDashboardIds.size > 0 && (
        <section className="card" style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <h3 style={{ margin: 0 }}>Important Dashboards ({usedDashboardIds.size})</h3>
            {savingUsed && <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Saving...</span>}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {storedDashboards
              .filter((d) => usedDashboardIds.has(d.dashboard_id))
              .map((d) => (
                <span
                  key={d.dashboard_id}
                  className="query-panel__chip"
                  onClick={() => toggleUsedDashboard(d.dashboard_id)}
                  title={`${d.dashboard_id} - click to remove`}
                  style={{ cursor: 'pointer' }}
                >
                  {d.title.length > 50 ? d.title.substring(0, 50) + '...' : d.title} &times;
                </span>
              ))}
          </div>
        </section>
      )}

      {/* Stored dashboards grouped by provider */}
      {storedDashboards.length > 0 && (
        <section className="card" style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h2 style={{ margin: 0 }}>Stored Dashboards ({storedDashboards.length})</h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {providerKeys.map((p) => (
                <ProviderBadge key={p} provider={p} />
              ))}
            </div>
          </div>

          {/* Local filter */}
          <input
            placeholder="Local filter by title or ID..."
            value={dashboardSearch}
            onChange={(e) => setDashboardSearch(e.target.value)}
            style={{ width: '100%', padding: '0.5rem 0.75rem', marginBottom: '0.5rem', boxSizing: 'border-box', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '0.9rem' }}
          />

          {/* Server-side wildcard search */}
          <div className="form-row" style={{ marginBottom: '0.75rem' }}>
            <input
              placeholder="Server search (supports * wildcard, leave empty to list all)..."
              value={serverSearch}
              onChange={(e) => setServerSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runServerSearch()}
              style={{ flex: 1, padding: '0.5rem 0.75rem', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '0.9rem' }}
            />
            <button className="btn-sm btn-primary-sm" onClick={runServerSearch} disabled={searching}>
              {searching ? 'Searching...' : serverSearch.trim() ? 'Search' : 'List All'}
            </button>
            {serverSearchResults && (
              <button className="btn-sm btn-outline" onClick={clearServerSearch}>
                Clear
              </button>
            )}
          </div>

          {serverSearchResults && (
            <div style={{ fontSize: '0.85em', color: '#3b82f6', marginBottom: '0.5rem', fontWeight: 500 }}>
              Server search: {serverSearchResults.length} result{serverSearchResults.length !== 1 ? 's' : ''} for "{serverSearch}"
            </div>
          )}

          {dashboardSearch && !serverSearchResults && (
            <div style={{ fontSize: '0.85em', color: '#666', marginBottom: '0.5rem' }}>
              Showing {Object.values(groupedDashboards).flat().length} of {storedDashboards.length}
            </div>
          )}

          {providerKeys.map((provider) => {
            const dashes = groupedDashboards[provider]
            const pc = getProviderColor(provider)
            return (
              <div key={provider} className="provider-section" style={{ borderLeftColor: pc.accent }}>
                <div className="provider-section__header" style={{ background: pc.bg }}>
                  <ProviderBadge provider={provider} />
                  <span className="provider-section__count">{dashes.length} dashboards</span>
                </div>

                <div className="provider-section__list">
                  {dashes.map((dash) => (
                    <div key={dash.id} className="dashboard-row">
                      <div className="dashboard-row__info">
                        <div className="dashboard-row__title">{dash.title}</div>
                        <div className="dashboard-row__meta">
                          ID: {dash.dashboard_id}
                          {dash.description && (
                            <span className="dashboard-row__desc"> — {dash.description.substring(0, 80)}</span>
                          )}
                        </div>
                      </div>
                      <div className="dashboard-row__actions">
                        <button
                          className={`btn-sm ${usedDashboardIds.has(dash.dashboard_id) ? 'btn-star--active' : 'btn-star'}`}
                          onClick={() => toggleUsedDashboard(dash.dashboard_id)}
                          title={usedDashboardIds.has(dash.dashboard_id) ? 'Remove from important' : 'Mark as important'}
                          disabled={savingUsed}
                        >
                          {usedDashboardIds.has(dash.dashboard_id) ? '\u2605' : '\u2606'}
                        </button>
                        <button
                          className="btn-sm"
                          onClick={() => extractMetrics(dash.dashboard_id)}
                          disabled={extracting === dash.dashboard_id}
                        >
                          {extracting === dash.dashboard_id ? 'Extracting...' : 'Extract Metrics'}
                        </button>
                        <button
                          className="btn-sm btn-outline"
                          onClick={() => viewMetrics(dash.id)}
                        >
                          {selectedDashId === dash.id ? 'Hide Metrics' : 'View Metrics'}
                        </button>
                        <button
                          className="btn-sm btn-outline"
                          onClick={() => loadTemplateVars(dash.id)}
                          disabled={loadingVarsDash === dash.id}
                        >
                          {loadingVarsDash === dash.id
                            ? 'Loading...'
                            : dashTemplateVars[dash.id]
                              ? 'Hide Variables'
                              : 'View Variables'}
                        </button>
                        <button
                          className="btn-sm btn-primary-sm"
                          onClick={() => openQueryPanel(dash)}
                          disabled={loadingQueryPanel === dash.id}
                        >
                          {loadingQueryPanel === dash.id
                            ? 'Loading...'
                            : queryPanelDashId === dash.id
                              ? 'Close Query'
                              : 'Query'}
                        </button>
                      </div>

                      {/* Template variables panel */}
                      {dashTemplateVars[dash.id] && (
                        <div className="metrics-panel" style={{ marginTop: '0.5rem' }}>
                          <TemplateVariablesPanel variables={dashTemplateVars[dash.id]} />
                        </div>
                      )}

                      {/* Query panel */}
                      {queryPanelDashId === dash.id && (
                        <div className="metrics-panel" style={{ marginTop: '0.5rem' }}>
                          <MetricQueryPanel
                            orgId={orgId}
                            dashboardId={dash.dashboard_id}
                            dashboardDbId={dash.id}
                            templateVariables={queryPanelVars.map((v) => ({
                              variable_name: v.variable_name,
                              tag_key: v.tag_key,
                              default_value: v.default_value,
                              values: v.values,
                            }))}
                            extractedMetrics={queryPanelMetrics.map((m) => ({
                              name: m.name,
                              details: m.details,
                            }))}
                            provider={providerFilter || undefined}
                          />
                        </div>
                      )}

                      {/* Metrics panel */}
                      {selectedDashId === dash.id && (
                        <div className="metrics-panel">
                          {selectedDashMetrics.length === 0 ? (
                            <div className="metrics-panel__empty">
                              No metrics extracted yet. Click "Extract Metrics" to start.
                            </div>
                          ) : (
                            <>
                              <div className="metrics-panel__header">
                                <strong>Extracted Metrics</strong>
                                <span className="metrics-panel__count">
                                  {selectedDashMetrics.length} widget{selectedDashMetrics.length !== 1 ? 's' : ''}
                                </span>
                              </div>
                              <div className="metrics-panel__list">
                                {selectedDashMetrics.map((metric) => (
                                  <MetricCard key={metric.id} metric={metric} />
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </section>
      )}
    </div>
  )
}
