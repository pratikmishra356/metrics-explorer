
interface ConfigProps {
  orgId: string
  setOrgId: (v: string) => void
  selectedProvider: string
  setSelectedProvider: (v: string) => void
  providerOptions: string[]
}

export function Config({
  orgId,
  setOrgId,
  selectedProvider,
  setSelectedProvider,
  providerOptions,
}: ConfigProps) {
  return (
    <section className="card config">
      <h2>Config</h2>
      <label>
        Organization ID (required for API calls)
        <input
          type="text"
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
        />
      </label>
      <label>
        Filter by provider (optional)
        <select
          value={selectedProvider}
          onChange={(e) => setSelectedProvider(e.target.value)}
        >
          <option value="">All providers</option>
          {providerOptions.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>
    </section>
  )
}
