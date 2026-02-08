import { useState } from 'react'
import { api } from '../api/client'
import type { Organization, CreateOrganizationRequest } from '../api/types'
import { ResponseViewer } from './ResponseViewer'

interface OrganizationManagerProps {
  orgId: string
  setOrgId: (v: string) => void
  onOrgChange: () => void
}

export function OrganizationManager({ orgId, setOrgId, onOrgChange }: OrganizationManagerProps) {
  const [createName, setCreateName] = useState('')
  const [createSlug, setCreateSlug] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<unknown>(null)
  const [status, setStatus] = useState('')
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loadingList, setLoadingList] = useState(false)

  const handleCreate = async () => {
    if (!createName.trim() || !createSlug.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const body: CreateOrganizationRequest = {
        name: createName.trim(),
        slug: createSlug.trim().toLowerCase().replace(/\s+/g, '-'),
      }
      if (createDesc.trim()) body.description = createDesc.trim()
      const { data } = await api.createOrganization(body)
      setResponse(data)
      setStatus('201 Created')
      setOrgId((data as Organization).id)
      onOrgChange()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  const handleGet = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const { data, status: s } = await api.getOrganization(orgId.trim())
      setResponse(data)
      setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  const handleListProviders = async () => {
    if (!orgId.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const { data, status: s } = await api.listOrganizationProviders(orgId.trim())
      setResponse(data)
      setStatus(`${s}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('Error')
    } finally {
      setLoading(false)
    }
  }

  const handleListOrganizations = async () => {
    setLoadingList(true)
    setError(null)
    try {
      const { data } = await api.listOrganizations({ limit: 100 })
      setOrganizations(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoadingList(false)
    }
  }

  const handleSelectOrganization = (selectedOrg: Organization) => {
    setOrgId(selectedOrg.id)
    onOrgChange()
  }

  return (
    <section className="card">
      <h2>Organizations</h2>
      
      {/* List Organizations Section */}
      <div style={{ marginBottom: '1.5rem' }}>
        <div className="form-row" style={{ marginBottom: '0.75rem' }}>
          <button onClick={handleListOrganizations} disabled={loadingList}>
            {loadingList ? 'Loading...' : 'List Organizations'}
          </button>
        </div>
        
        {organizations.length > 0 && (
          <div style={{ border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.75rem', background: '#f8fafc' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem', color: '#475569' }}>
              Available Organizations ({organizations.length})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto' }}>
              {organizations.map((org) => (
                <div
                  key={org.id}
                  onClick={() => handleSelectOrganization(org)}
                  style={{
                    padding: '0.75rem',
                    borderRadius: '4px',
                    border: org.id === orgId ? '2px solid #3b82f6' : '1px solid #e2e8f0',
                    background: org.id === orgId ? '#eff6ff' : 'white',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (org.id !== orgId) {
                      e.currentTarget.style.background = '#f1f5f9'
                      e.currentTarget.style.borderColor = '#cbd5e1'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (org.id !== orgId) {
                      e.currentTarget.style.background = 'white'
                      e.currentTarget.style.borderColor = '#e2e8f0'
                    }
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: '0.25rem' }}>
                        {org.name}
                        {org.id === orgId && (
                          <span style={{ marginLeft: '0.5rem', fontSize: '0.85rem', color: '#3b82f6', fontWeight: 500 }}>
                            (Selected)
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '0.25rem' }}>
                        Slug: <code style={{ background: '#f1f5f9', padding: '0.1rem 0.3rem', borderRadius: '3px' }}>{org.slug}</code>
                      </div>
                      {org.description && (
                        <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.25rem' }}>
                          {org.description.length > 100 ? `${org.description.substring(0, 100)}...` : org.description}
                        </div>
                      )}
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.5rem' }}>
                        ID: {org.id.substring(0, 8)}... | Providers: {org.providers.length} | Used Dashboards: {org.used_dashboards?.length || 0}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Create Organization Section */}
      <div style={{ marginBottom: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid #e2e8f0' }}>
        <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1.1rem' }}>Create New Organization</h3>
        <div className="form-row">
          <input
            placeholder="Organization name"
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
          />
          <input
            placeholder="Slug (e.g. my-org)"
            value={createSlug}
            onChange={(e) => setCreateSlug(e.target.value)}
          />
          <input
            placeholder="Description (optional)"
            value={createDesc}
            onChange={(e) => setCreateDesc(e.target.value)}
          />
          <button onClick={handleCreate} disabled={loading || !createName.trim() || !createSlug.trim()}>
            Create organization
          </button>
        </div>
      </div>

      {/* Actions Section */}
      <div style={{ paddingTop: '1.5rem', borderTop: '1px solid #e2e8f0' }}>
        <div className="form-row">
          <input
            placeholder="Organization ID"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            style={{ flex: 1 }}
          />
          <button onClick={handleGet} disabled={loading || !orgId.trim()}>
            Get organization
          </button>
          <button onClick={handleListProviders} disabled={loading || !orgId.trim()}>
            List providers for org
          </button>
        </div>
      </div>

      <ResponseViewer data={response} status={status} error={error} loading={loading} />
    </section>
  )
}
