import { Monitors } from '../components/Monitors'
import { useAppContext } from '../context/AppContext'

export function MonitorsPage() {
  const { orgId, selectedProvider } = useAppContext()
  return <Monitors orgId={orgId} providerFilter={selectedProvider} />
}
