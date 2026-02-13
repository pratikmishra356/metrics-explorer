import { Config } from '../components/Config'
import { useAppContext } from '../context/AppContext'
import { Link } from 'react-router-dom'

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
        <h2>Welcome to Metrics Explorer</h2>
        <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1rem' }}>
          A provider-agnostic metrics exploration platform that connects to Datadog, Prometheus, and Grafana.
        </p>
        {orgId && (
          <div style={{ 
            padding: '0.75rem', 
            background: '#eff6ff', 
            border: '1px solid #bfdbfe', 
            borderRadius: '6px',
            marginBottom: '1rem'
          }}>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>
              <strong>Active Org ID:</strong>{' '}
              <code style={{ background: '#dbeafe', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>
                {orgId}
              </code>
            </p>
          </div>
        )}
      </section>

      {/* Setup Instructions */}
      <section className="card" style={{ marginTop: '1rem' }}>
        <h2 style={{ marginTop: 0 }}>Getting Started</h2>
        <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
          Follow these steps to set up your organization and start exploring metrics:
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Step 1 */}
          <div style={{ 
            borderLeft: '3px solid #3b82f6', 
            paddingLeft: '1rem',
            paddingBottom: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: '#3b82f6',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.9rem',
                flexShrink: 0
              }}>
                1
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>
                Create or Select an Organization
              </h3>
            </div>
            <div style={{ marginLeft: '2.75rem', color: '#475569', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.25rem 0' }}>
                Navigate to the <Link to="/organizations" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>Organizations</Link> page:
              </p>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: '1.6' }}>
                <li>Click <strong>"List Organizations"</strong> to see existing organizations</li>
                <li>Click on an organization to select it, or</li>
                <li>Create a new organization by filling in:
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li><strong>Name:</strong> Display name (e.g., "My Company")</li>
                    <li><strong>Slug:</strong> URL-friendly identifier (e.g., "my-company")</li>
                    <li><strong>Description:</strong> Optional description</li>
                  </ul>
                </li>
              </ul>
            </div>
          </div>

          {/* Step 2 */}
          <div style={{ 
            borderLeft: '3px solid #10b981', 
            paddingLeft: '1rem',
            paddingBottom: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: '#10b981',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.9rem',
                flexShrink: 0
              }}>
                2
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>
                Add a Provider Configuration
              </h3>
            </div>
            <div style={{ marginLeft: '2.75rem', color: '#475569', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.25rem 0' }}>
                On the <Link to="/organizations" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>Organizations</Link> page, add a provider:
              </p>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: '1.6' }}>
                <li>Select your provider type: <strong>Datadog</strong>, <strong>Prometheus</strong>, or <strong>Grafana</strong></li>
                <li>Enter provider credentials:
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li><strong>Datadog:</strong> API Key, Application Key, and Site (e.g., datadoghq.com)</li>
                    <li><strong>Prometheus:</strong> Endpoint URL and authentication (username/password or bearer token)</li>
                    <li><strong>Grafana:</strong> Endpoint URL and API Key</li>
                  </ul>
                </li>
                <li>Click <strong>"Add Provider"</strong> to save the configuration</li>
              </ul>
            </div>
          </div>

          {/* Step 3 */}
          <div style={{ 
            borderLeft: '3px solid #f59e0b', 
            paddingLeft: '1rem',
            paddingBottom: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: '#f59e0b',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.9rem',
                flexShrink: 0
              }}>
                3
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>
                Sync Dashboards from Provider
              </h3>
            </div>
            <div style={{ marginLeft: '2.75rem', color: '#475569', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.25rem 0' }}>
                Go to the <Link to="/dashboards" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>Dashboards</Link> page:
              </p>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: '1.6' }}>
                <li>Click <strong>"Sync from Providers"</strong> to fetch dashboards from your configured providers</li>
                <li>This will retrieve all dashboards available in your provider account</li>
                <li>Dashboards will be stored locally for faster access</li>
              </ul>
            </div>
          </div>

          {/* Step 4 */}
          <div style={{ 
            borderLeft: '3px solid #8b5cf6', 
            paddingLeft: '1rem',
            paddingBottom: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: '#8b5cf6',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.9rem',
                flexShrink: 0
              }}>
                4
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>
                Extract Metrics from Dashboards
              </h3>
            </div>
            <div style={{ marginLeft: '2.75rem', color: '#475569', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.25rem 0' }}>
                On the <Link to="/dashboards" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>Dashboards</Link> page:
              </p>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: '1.6' }}>
                <li>Find a dashboard you want to analyze</li>
                <li>Click <strong>"Extract Metrics"</strong> on any dashboard</li>
                <li>This will:
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li>Extract all metric queries from dashboard widgets</li>
                    <li>Resolve template variables (e.g., <code style={{ background: '#f1f5f9', padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.85em' }}>$env</code>, <code style={{ background: '#f1f5f9', padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.85em' }}>$service</code>)</li>
                    <li>Store resolved values for filtering</li>
                  </ul>
                </li>
                <li>Click <strong>"View Metrics"</strong> to see extracted metrics</li>
                <li>Click <strong>"View Variables"</strong> to see resolved template variables</li>
              </ul>
            </div>
          </div>

          {/* Step 5 */}
          <div style={{ 
            borderLeft: '3px solid #ec4899', 
            paddingLeft: '1rem',
            paddingBottom: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: '#ec4899',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.9rem',
                flexShrink: 0
              }}>
                5
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>
                Query Metrics with Filters
              </h3>
            </div>
            <div style={{ marginLeft: '2.75rem', color: '#475569', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.25rem 0' }}>
                On the <Link to="/dashboards" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>Dashboards</Link> page:
              </p>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: '1.6' }}>
                <li>Click <strong>"Query"</strong> on any dashboard</li>
                <li>In the query panel:
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li>Select metrics to query</li>
                    <li>Choose aggregation (avg, sum, min, max, etc.)</li>
                    <li>Set time range (15m, 1h, 4h, 24h, 7d)</li>
                    <li>Apply template variable filters (e.g., environment, service)</li>
                    <li>Add group-by tags for breakdown</li>
                  </ul>
                </li>
                <li>Click <strong>"Execute Query"</strong> to fetch time series data</li>
                <li>View results with data points and series breakdown</li>
              </ul>
            </div>
          </div>

          {/* Step 6 */}
          <div style={{ 
            borderLeft: '3px solid #06b6d4', 
            paddingLeft: '1rem',
            paddingBottom: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: '#06b6d4',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.9rem',
                flexShrink: 0
              }}>
                6
              </div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>
                Mark and Manage Important Dashboards
              </h3>
            </div>
            <div style={{ marginLeft: '2.75rem', color: '#475569', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.25rem 0' }}>
                On the <Link to="/dashboards" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 500 }}>Dashboards</Link> page:
              </p>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: '1.6' }}>
                <li><strong>Marking Important Dashboards:</strong>
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li>Click the <strong>star icon</strong> (★) on any dashboard row to mark it as important</li>
                    <li>The star will turn yellow/gold when active</li>
                    <li>Click again to unmark if needed</li>
                    <li>Mark dashboards you use frequently or are critical for monitoring</li>
                  </ul>
                </li>
                <li><strong>Viewing Important Dashboards:</strong>
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li>All marked dashboards appear in the <strong>"Important Dashboards"</strong> section at the top</li>
                    <li>This section shows a quick summary of your starred dashboards</li>
                    <li>Click on any dashboard name in this section to remove it from important</li>
                  </ul>
                </li>
                <li><strong>Benefits of Marking Important Dashboards:</strong>
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li>These dashboards are prioritized in API responses for AI agents</li>
                    <li>Helps AI understand which dashboards are most relevant to your organization</li>
                    <li>Makes it easier to find frequently used dashboards</li>
                    <li>The <code style={{ background: '#f1f5f9', padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.85em' }}>used_dashboards</code> field in organization API helps filter noise</li>
                  </ul>
                </li>
                <li><strong>Searching Dashboards:</strong>
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1.25rem' }}>
                    <li>Use the <strong>"Server search"</strong> bar with wildcards (e.g., <code style={{ background: '#f1f5f9', padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.85em' }}>*DynamoDB*</code>) to find dashboards quickly</li>
                    <li>Leave search empty and click <strong>"List All"</strong> to see all dashboards</li>
                    <li>Search works on dashboard titles and IDs</li>
                  </ul>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Important Dashboards Tip */}
        <div style={{ 
          marginTop: '2rem', 
          padding: '1rem 1.25rem', 
          background: 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)',
          borderRadius: '8px',
          border: '2px solid #3b82f6',
          boxShadow: '0 2px 4px rgba(59, 130, 246, 0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <div style={{ 
              fontSize: '1.5rem', 
              lineHeight: '1',
              flexShrink: 0,
              marginTop: '0.1rem'
            }}>
              💡
            </div>
            <div style={{ flex: 1 }}>
              <h3 style={{ 
                margin: '0 0 0.5rem 0', 
                fontSize: '1rem', 
                color: '#1e40af',
                fontWeight: 600
              }}>
                Pro Tip: Manage Important Dashboards
              </h3>
              <p style={{ 
                margin: '0 0 0.75rem 0', 
                color: '#1e3a8a', 
                fontSize: '0.9rem',
                lineHeight: '1.6'
              }}>
                Marking important dashboards helps AI agents and automation tools understand which dashboards are most relevant to your organization. When you mark dashboards as important:
              </p>
              <ul style={{ 
                margin: 0, 
                paddingLeft: '1.5rem', 
                color: '#1e3a8a',
                fontSize: '0.9rem',
                lineHeight: '1.8'
              }}>
                <li>They appear in the <code style={{ background: 'rgba(255,255,255,0.7)', padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.85em', fontWeight: 500 }}>used_dashboards</code> field when querying the organization API</li>
                <li>AI agents can prioritize these dashboards when exploring your metrics</li>
                <li>Reduces noise in API responses by focusing on what matters most</li>
                <li>Makes it easier to discover and navigate frequently used dashboards</li>
              </ul>
              <p style={{ 
                margin: '0.75rem 0 0 0', 
                color: '#1e3a8a', 
                fontSize: '0.85rem',
                fontStyle: 'italic'
              }}>
                💡 <strong>Best Practice:</strong> Mark 5-10 of your most critical dashboards rather than marking everything. This ensures the signal-to-noise ratio remains high.
              </p>
            </div>
          </div>
        </div>

        {/* Quick Links */}
        <div style={{ 
          marginTop: '2rem', 
          padding: '1rem', 
          background: '#f8fafc', 
          borderRadius: '6px',
          border: '1px solid #e2e8f0'
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1rem', color: '#1e293b' }}>
            Quick Links
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            <Link 
              to="/organizations" 
              style={{ 
                padding: '0.5rem 1rem', 
                background: 'white', 
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                textDecoration: 'none',
                color: '#475569',
                fontSize: '0.9rem',
                fontWeight: 500,
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f1f5f9'
                e.currentTarget.style.borderColor = '#94a3b8'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'white'
                e.currentTarget.style.borderColor = '#cbd5e1'
              }}
            >
              📋 Organizations
            </Link>
            <Link 
              to="/dashboards" 
              style={{ 
                padding: '0.5rem 1rem', 
                background: 'white', 
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                textDecoration: 'none',
                color: '#475569',
                fontSize: '0.9rem',
                fontWeight: 500,
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f1f5f9'
                e.currentTarget.style.borderColor = '#94a3b8'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'white'
                e.currentTarget.style.borderColor = '#cbd5e1'
              }}
            >
              📊 Dashboards
            </Link>
            <Link 
              to="/monitors" 
              style={{ 
                padding: '0.5rem 1rem', 
                background: 'white', 
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                textDecoration: 'none',
                color: '#475569',
                fontSize: '0.9rem',
                fontWeight: 500,
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f1f5f9'
                e.currentTarget.style.borderColor = '#94a3b8'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'white'
                e.currentTarget.style.borderColor = '#cbd5e1'
              }}
            >
              🔔 Monitors
            </Link>
            <Link 
              to="/metrics" 
              style={{ 
                padding: '0.5rem 1rem', 
                background: 'white', 
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                textDecoration: 'none',
                color: '#475569',
                fontSize: '0.9rem',
                fontWeight: 500,
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f1f5f9'
                e.currentTarget.style.borderColor = '#94a3b8'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'white'
                e.currentTarget.style.borderColor = '#cbd5e1'
              }}
            >
              📈 Metrics
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
