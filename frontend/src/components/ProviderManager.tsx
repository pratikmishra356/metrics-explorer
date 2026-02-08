import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { ProviderType } from '../api/types'
import { ResponseViewer } from './ResponseViewer'

const PROVIDER_TYPES: ProviderType[] = ['datadog', 'prometheus', 'grafana']

interface ProviderManagerProps {
  orgId: string
  onProviderChange: () => void
}

export function ProviderManager({ orgId, onProviderChange }: ProviderManagerProps) {
  const [providerType, setProviderType] = useState<ProviderType>('datadog')
  const [name, setName] = useState('default')
  const [endpointUrl, setEndpointUrl] = useState('')
  const [credentialsJson, setCredentialsJson] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<unknown>(null)
  const [status, setStatus] = useState('')

  const getDefaultCredentials = (): Record<string, string> => {
    switch (providerType) {
      case 'datadog':
        return { api_key: '', app_key: '', site: 'datadoghq.com' }
      case 'prometheus':
        return { url: 'http://localhost:9090', username: '', password: '' }
      case 'grafana':
        return { url: 'http://localhost:3000', api_key: '' }
      default:
        return {}
    }
  }

  useEffect(() => {
    setCredentialsJson(JSON.stringify(getDefaultCredentials(), null, 2))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerType])

  const handleAdd = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      let credentials: Record<string, string>
      try {
        credentials = credentialsJson.trim()
          ? (JSON.parse(credentialsJson) as Record<string, string>)
          : getDefaultCredentials()
      } catch {
        setError('Invalid JSON in credentials')
        setLoading(false)
        return
      }
      const { data, status: s } = await api.addProvider(orgId.trim(), {
        provider_type: providerType,
        name: name.trim() || 'default',
        endpoint_url: endpointUrl.trim() || undefined,
        credentials,
      })
      setResponse(data)
      setStatus(`${s} Created`)
      onProviderChange()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>Add provider to organization</h2>
      <p className="hint">Set Organization ID above, then add a provider. Credentials are stored encrypted.</p>
      <div className="form-row">
        <label>
          Provider type
          <select
            value={providerType}
            onChange={(e) => {
              setProviderType(e.target.value as ProviderType)
              setCredentialsJson(JSON.stringify(getDefaultCredentials(), null, 2))
            }}
          >
            {PROVIDER_TYPES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="default" />
        </label>
        <label>
          Endpoint URL (optional for Datadog)
          <input
            value={endpointUrl}
            onChange={(e) => setEndpointUrl(e.target.value)}
            placeholder={providerType === 'prometheus' ? 'http://localhost:9090' : providerType === 'grafana' ? 'http://localhost:3000' : ''}
          />
        </label>
      </div>
      <label>
        Credentials (JSON)
        <textarea
          value={credentialsJson || JSON.stringify(getDefaultCredentials(), null, 2)}
          onChange={(e) => setCredentialsJson(e.target.value)}
          rows={6}
          placeholder="{}"
          className="credentials-input"
        />
      </label>
      <div className="form-row">
        <button onClick={handleAdd} disabled={loading || !orgId.trim()}>
          Add provider
        </button>
      </div>
      <ResponseViewer data={response} status={status} error={error} loading={loading} />
    </section>
  )
}
