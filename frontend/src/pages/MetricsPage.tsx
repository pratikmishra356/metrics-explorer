import { Metrics } from '../components/Metrics'
import { useAppContext } from '../context/AppContext'

export function MetricsPage() {
  const { orgId, selectedProvider } = useAppContext()
  return <Metrics orgId={orgId} providerFilter={selectedProvider} />
}
