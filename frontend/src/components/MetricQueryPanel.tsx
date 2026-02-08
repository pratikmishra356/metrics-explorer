import { useState, useMemo } from 'react'
import { api } from '../api/client'
import type {
  DashboardQueryRequest,
  DashboardQueryResponse,
  QueryResultItem,
  QuerySeries,
} from '../api/types'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface TemplateVar {
  variable_name: string
  tag_key: string
  default_value: string | null
  values: string[]
}

interface ExtractedMetric {
  name: string | null
  details: Record<string, unknown>
}

interface MetricQueryPanelProps {
  orgId: string
  dashboardId: string          // provider dashboard ID (e.g. "4k2-qvg-h38")
  dashboardDbId: string        // internal DB ID
  templateVariables: TemplateVar[]
  extractedMetrics: ExtractedMetric[]
  provider?: string
}

/* ------------------------------------------------------------------ */
/*  Time range presets                                                  */
/* ------------------------------------------------------------------ */

const TIME_PRESETS = [
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '4h', value: '4h' },
  { label: '24h', value: '24h' },
  { label: '3d', value: '3d' },
  { label: '7d', value: '7d' },
]

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Extract distinct metric names from extracted metrics' query strings. */
function extractMetricNames(metrics: ExtractedMetric[]): string[] {
  const names = new Set<string>()
  const pattern = /(?:avg|sum|min|max|count|last|p\d+):([a-zA-Z][a-zA-Z0-9_.]+)\{/g
  for (const m of metrics) {
    const requests = (m.details?.requests ?? []) as Array<Record<string, unknown>>
    for (const req of requests) {
      const queries = (req.queries ?? []) as Array<Record<string, unknown>>
      for (const q of queries) {
        const qs = (q.query as string) ?? ''
        let match: RegExpExecArray | null
        pattern.lastIndex = 0
        while ((match = pattern.exec(qs)) !== null) {
          names.add(match[1])
        }
      }
    }
  }
  return Array.from(names).sort()
}

function formatTimestamp(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatValue(v: number | null): string {
  if (v === null || v === undefined) return '—'
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M'
  if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(2) + 'K'
  return Number.isInteger(v) ? String(v) : v.toFixed(4)
}

/* ------------------------------------------------------------------ */
/*  Series Result Card                                                 */
/* ------------------------------------------------------------------ */

function SeriesCard({ series, index }: { series: QuerySeries; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const tagEntries = Object.entries(series.tags)
  const dpCount = series.datapoints.length
  const last = dpCount > 0 ? series.datapoints[dpCount - 1] : null
  const avg =
    dpCount > 0
      ? series.datapoints.reduce((s, d) => s + (d.value ?? 0), 0) / dpCount
      : null

  return (
    <div className="series-card">
      <div className="series-card__header" onClick={() => setExpanded(!expanded)}>
        <span className="series-card__index">#{index + 1}</span>
        <span className="series-card__scope">
          {tagEntries.length > 0
            ? tagEntries.map(([k, v]) => `${k}:${v}`).join(', ')
            : series.scope || '*'}
        </span>
        <span className="series-card__stats">
          {dpCount} pts
          {last && <> | last: <strong>{formatValue(last.value)}</strong></>}
          {avg !== null && <> | avg: <strong>{formatValue(avg)}</strong></>}
          {series.unit && <> ({series.unit})</>}
        </span>
        <span className="series-card__toggle">{expanded ? '\u25BC' : '\u25B6'}</span>
      </div>
      {expanded && (
        <div className="series-card__body">
          <table className="series-card__table">
            <thead>
              <tr><th>Time</th><th>Value</th></tr>
            </thead>
            <tbody>
              {series.datapoints.slice(-50).map((dp, i) => (
                <tr key={i}>
                  <td>{formatTimestamp(dp.timestamp)}</td>
                  <td>{formatValue(dp.value)}</td>
                </tr>
              ))}
              {dpCount > 50 && (
                <tr><td colSpan={2} style={{ textAlign: 'center', color: '#94a3b8' }}>
                  ... {dpCount - 50} earlier points hidden
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Query Result Card                                                  */
/* ------------------------------------------------------------------ */

function QueryResultCard({ result }: { result: QueryResultItem }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className={`query-result ${result.error ? 'query-result--error' : ''}`}>
      <div className="query-result__header" onClick={() => setExpanded(!expanded)}>
        <span className="query-result__toggle">{expanded ? '\u25BC' : '\u25B6'}</span>
        <strong>{result.metric_name}</strong>
        <span className="query-result__stats">
          {result.series_count} series | {result.datapoint_count} points | {result.query_time_ms}ms
        </span>
        {result.error && <span className="query-result__error-badge">ERROR</span>}
      </div>
      {result.expression && (
        <code className="query-result__expression">{result.expression}</code>
      )}
      {result.error && <div className="query-result__error-msg">{result.error}</div>}
      {expanded && result.series.length > 0 && (
        <div className="query-result__series">
          {result.series.map((s, i) => (
            <SeriesCard key={i} series={s} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Panel                                                         */
/* ------------------------------------------------------------------ */

export function MetricQueryPanel({
  orgId,
  dashboardId,
  dashboardDbId: _dashboardDbId,
  templateVariables,
  extractedMetrics,
  provider,
}: MetricQueryPanelProps) {
  // Available metric names extracted from stored widget queries
  const metricNames = useMemo(() => extractMetricNames(extractedMetrics), [extractedMetrics])

  // Query state
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])
  const [metricSearch, setMetricSearch] = useState('')
  const [aggregation, setAggregation] = useState('avg')
  const [groupBy, setGroupBy] = useState<string[]>([])
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [timePreset, setTimePreset] = useState('1h')
  const [executing, setExecuting] = useState(false)
  const [response, setResponse] = useState<DashboardQueryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Filtered metric name list for the dropdown
  const filteredMetrics = useMemo(() => {
    if (!metricSearch.trim()) return metricNames
    const q = metricSearch.toLowerCase()
    return metricNames.filter((n) => n.toLowerCase().includes(q))
  }, [metricNames, metricSearch])

  /* ---- Actions ---- */

  const toggleMetric = (name: string) => {
    setSelectedMetrics((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    )
  }

  const toggleGroupBy = (key: string) => {
    setGroupBy((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  }

  const setFilter = (key: string, value: string) => {
    setFilters((prev) => {
      const next = { ...prev }
      if (!value || value === '*') {
        delete next[key]
      } else {
        next[key] = value
      }
      return next
    })
  }

  const executeQuery = async () => {
    if (selectedMetrics.length === 0) return
    setExecuting(true)
    setError(null)
    setResponse(null)

    const body: DashboardQueryRequest = {
      queries: selectedMetrics.map((metric) => ({
        metric_name: metric,
        aggregation,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
        group_by: groupBy.length > 0 ? groupBy : undefined,
      })),
      time_range: { relative: timePreset },
    }

    try {
      const { data } = await api.queryDashboardMetrics(orgId, dashboardId, body, provider)
      setResponse(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setExecuting(false)
    }
  }

  /* ---- Render ---- */

  return (
    <div className="query-panel">
      <div className="query-panel__header">
        <h3>Query Metrics</h3>
      </div>

      <div className="query-panel__body">
        {/* Metric selection */}
        <div className="query-panel__section">
          <label className="query-panel__label">
            Metrics
            {selectedMetrics.length > 0 && (
              <span className="query-panel__badge">{selectedMetrics.length} selected</span>
            )}
          </label>
          <input
            className="query-panel__search"
            placeholder="Search metrics..."
            value={metricSearch}
            onChange={(e) => setMetricSearch(e.target.value)}
          />
          <div className="query-panel__metric-list">
            {filteredMetrics.slice(0, 50).map((name) => (
              <label key={name} className="query-panel__metric-item">
                <input
                  type="checkbox"
                  checked={selectedMetrics.includes(name)}
                  onChange={() => toggleMetric(name)}
                />
                <code>{name}</code>
              </label>
            ))}
            {filteredMetrics.length > 50 && (
              <div className="query-panel__more">... {filteredMetrics.length - 50} more</div>
            )}
            {filteredMetrics.length === 0 && (
              <div className="query-panel__empty">No metrics found</div>
            )}
          </div>
        </div>

        {/* Aggregation + Time range */}
        <div className="query-panel__row">
          <div className="query-panel__section query-panel__section--half">
            <label className="query-panel__label">Aggregation</label>
            <select
              className="query-panel__select"
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value)}
            >
              {['avg', 'sum', 'min', 'max', 'count'].map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div className="query-panel__section query-panel__section--half">
            <label className="query-panel__label">Time Range</label>
            <div className="query-panel__presets">
              {TIME_PRESETS.map((p) => (
                <button
                  key={p.value}
                  className={`query-panel__preset ${timePreset === p.value ? 'query-panel__preset--active' : ''}`}
                  onClick={() => setTimePreset(p.value)}
                  type="button"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Template variable filters */}
        {templateVariables.length > 0 && (
          <div className="query-panel__section">
            <label className="query-panel__label">
              Variable Filters
              <span className="query-panel__hint">(leave empty for all values)</span>
            </label>
            <div className="query-panel__filters">
              {templateVariables.map((tv) => (
                <div key={tv.variable_name} className="query-panel__filter-row">
                  <code className="query-panel__filter-name">${tv.variable_name}</code>
                  {tv.values.length > 0 && tv.values.length <= 200 ? (
                    <select
                      className="query-panel__filter-select"
                      value={filters[tv.tag_key] ?? ''}
                      onChange={(e) => setFilter(tv.tag_key, e.target.value)}
                    >
                      <option value="">All ({tv.values.length})</option>
                      {tv.values.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="query-panel__filter-input"
                      placeholder={
                        tv.values.length > 200
                          ? `Type value (${tv.values.length} available)`
                          : 'Type value...'
                      }
                      value={filters[tv.tag_key] ?? ''}
                      onChange={(e) => setFilter(tv.tag_key, e.target.value)}
                    />
                  )}
                  <button
                    className="query-panel__filter-group-toggle"
                    onClick={() => toggleGroupBy(tv.tag_key)}
                    type="button"
                    title={groupBy.includes(tv.tag_key) ? 'Remove from group-by' : 'Add to group-by'}
                  >
                    {groupBy.includes(tv.tag_key) ? 'Grouped' : 'Group'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Group by display */}
        {groupBy.length > 0 && (
          <div className="query-panel__section">
            <label className="query-panel__label">Group By</label>
            <div className="query-panel__chips">
              {groupBy.map((g) => (
                <span
                  key={g}
                  className="query-panel__chip"
                  onClick={() => toggleGroupBy(g)}
                  title="Click to remove"
                >
                  {g} &times;
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Execute */}
        <div className="query-panel__actions">
          <button
            className="btn-primary"
            onClick={executeQuery}
            disabled={executing || selectedMetrics.length === 0}
          >
            {executing ? 'Executing...' : `Execute Query (${selectedMetrics.length} metric${selectedMetrics.length !== 1 ? 's' : ''})`}
          </button>
          {selectedMetrics.length === 0 && (
            <span className="query-panel__hint">Select at least one metric</span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="query-panel__error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Results */}
      {response && (
        <div className="query-panel__results">
          <div className="query-panel__results-header">
            <h4>Results</h4>
            <span className="query-panel__results-stats">
              {response.total_queries} queries |{' '}
              {response.total_series} series |{' '}
              {response.total_datapoints} points |{' '}
              {response.execution_time_ms}ms |{' '}
              provider: {response.provider}
            </span>
          </div>
          {response.results.map((r) => (
            <QueryResultCard key={r.query_index} result={r} />
          ))}
        </div>
      )}
    </div>
  )
}
