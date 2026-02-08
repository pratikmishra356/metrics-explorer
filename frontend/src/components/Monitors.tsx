import { useState } from 'react'
import { api } from '../api/client'
import { ResponseViewer } from './ResponseViewer'

interface MonitorsProps {
  orgId: string
  providerFilter: string
}

export function Monitors({ orgId, providerFilter }: MonitorsProps) {
  const [monitorId, setMonitorId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<unknown>(null)
  const [status, setStatus] = useState('')

  const listMonitors = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const params: Record<string, string> = {}
      if (providerFilter) params.provider = providerFilter
      const { data, status: s } = await api.listMonitors(orgId.trim(), params as { provider?: string })
      setResponse(data)
      setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  const getMonitor = async () => {
    if (!orgId.trim() || !monitorId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const { data, status: s } = await api.getMonitor(
        orgId.trim(),
        monitorId.trim(),
        providerFilter || undefined
      )
      setResponse(data)
      setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>Monitors</h2>
      <div className="form-row">
        <button onClick={listMonitors} disabled={loading || !orgId.trim()}>
          List monitors
        </button>
      </div>
      <div className="form-row">
        <input
          placeholder="Monitor ID"
          value={monitorId}
          onChange={(e) => setMonitorId(e.target.value)}
        />
        <button onClick={getMonitor} disabled={loading || !orgId.trim() || !monitorId.trim()}>
          Get monitor
        </button>
      </div>
      <ResponseViewer data={response} status={status} error={error} loading={loading} />
    </section>
  )
}
