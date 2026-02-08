
interface ResponseViewerProps {
  data: unknown
  status?: string
  error?: string | null
  loading?: boolean
}

export function ResponseViewer({ data, status, error, loading }: ResponseViewerProps) {
  if (loading) {
    return (
      <pre className="response response-loading">
        Loading…
      </pre>
    )
  }
  if (error) {
    return (
      <>
        {status && <div className="response-status error">{status}</div>}
        <pre className="response response-error">{error}</pre>
      </>
    )
  }
  const text = data === undefined || data === null
    ? '(no response)'
    : typeof data === 'string'
      ? data
      : JSON.stringify(data, null, 2)
  return (
    <>
      {status && <div className="response-status">{status}</div>}
      <pre className="response">{text}</pre>
    </>
  )
}
