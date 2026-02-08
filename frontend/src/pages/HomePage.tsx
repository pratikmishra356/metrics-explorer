import { Config } from '../components/Config'
import { useAppContext } from '../context/AppContext'

export function HomePage() {
  const { orgId, setOrgId, selectedProvider, setSelectedProvider, providerOptions } =
    useAppContext()

  return (
    <>
      <Config
        orgId={orgId}
        setOrgId={setOrgId}
        selectedProvider={selectedProvider}
        setSelectedProvider={setSelectedProvider}
        providerOptions={providerOptions}
      />
      <section className="card" style={{ marginTop: '1rem' }}>
        <h2>Welcome</h2>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
          Set your organization ID and optional provider filter above, then use the
          navigation bar to explore organizations, dashboards, monitors, and metrics.
        </p>
        {orgId && (
          <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>
            <strong>Active Org ID:</strong>{' '}
            <code style={{ background: '#f1f5f9', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>
              {orgId}
            </code>
          </p>
        )}
      </section>
    </>
  )
}
