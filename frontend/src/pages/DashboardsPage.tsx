import { Dashboards } from '../components/Dashboards'
import { useAppContext } from '../context/AppContext'

export function DashboardsPage() {
  const { orgId, selectedProvider } = useAppContext()
  return <Dashboards orgId={orgId} providerFilter={selectedProvider} />
}
