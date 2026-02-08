const PROVIDER_COLORS: Record<string, { bg: string; text: string; border: string; accent: string }> = {
  datadog: { bg: '#f5f0ff', text: '#6b21a8', border: '#d8b4fe', accent: '#7c3aed' },
  prometheus: { bg: '#fef2f2', text: '#991b1b', border: '#fca5a5', accent: '#dc2626' },
  grafana: { bg: '#fefce8', text: '#854d0e', border: '#fde047', accent: '#ca8a04' },
}

const DEFAULT_PROVIDER_COLOR = { bg: '#f8fafc', text: '#475569', border: '#cbd5e1', accent: '#64748b' }

export function ProviderBadge({ provider }: { provider: string }) {
  const c = PROVIDER_COLORS[provider.toLowerCase()] || DEFAULT_PROVIDER_COLOR
  return (
    <span
      className="provider-badge"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
    >
      {provider}
    </span>
  )
}
