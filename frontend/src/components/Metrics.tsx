import { useState } from 'react'
import { api } from '../api/client'
import { ResponseViewer } from './ResponseViewer'

interface MetricsProps {
  orgId: string
  providerFilter: string
}

function toISOLocal(d: Date) {
  return d.toISOString().slice(0, 19)
}

export function Metrics({ orgId, providerFilter }: MetricsProps) {
  const [metricNames, setMetricNames] = useState('')
  const [startTime, setStartTime] = useState(() => {
    const d = new Date()
    d.setHours(d.getHours() - 1)
    return toISOLocal(d)
  })
  const [endTime, setEndTime] = useState(() => toISOLocal(new Date()))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<unknown>(null)
  const [status, setStatus] = useState('')

  const queryMetrics = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const names = metricNames.trim().split(',').map((s) => s.trim()).filter(Boolean)
      const { data, status: resStatus } = await api.queryMetrics(orgId.trim(), {
        metric_names: names.length ? names : undefined,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        step_seconds: 60,
      })
      setResponse(data)
      setStatus(String(resStatus))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  const getMetadata = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const params: Record<string, string> = {}
      if (providerFilter) params.provider = providerFilter
      const { data, status: resStatus } = await api.getMetricsMetadata(orgId.trim(), params as { provider?: string })
      setResponse(data)
      setStatus(String(resStatus))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  const listProviders = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const { data, status: resStatus } = await api.listProviders(orgId.trim())
      setResponse(data)
      setStatus(String(resStatus))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>Metrics</h2>
      <div className="form-row">
        <input
          placeholder="Metric names (comma-separated)"
          value={metricNames}
          onChange={(e) => setMetricNames(e.target.value)}
        />
        <input
          type="datetime-local"
          value={startTime}
          onChange={(e) => setStartTime(e.target.value)}
        />
        <input
          type="datetime-local"
          value={endTime}
          onChange={(e) => setEndTime(e.target.value)}
        />
      </div>
      <div className="form-row">
        <button onClick={queryMetrics} disabled={loading || !orgId.trim()}>
          Query metrics
        </button>
        <button onClick={getMetadata} disabled={loading || !orgId.trim()}>
          Get metadata
        </button>
        <button onClick={listProviders} disabled={loading || !orgId.trim()}>
          List providers
        </button>
      </div>
      <ResponseViewer data={response} status={status} error={error} loading={loading} />
    </section>
  )
}
