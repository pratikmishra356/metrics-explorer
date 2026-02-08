import { OrganizationManager } from '../components/OrganizationManager'
import { ProviderManager } from '../components/ProviderManager'
import { useAppContext } from '../context/AppContext'

export function OrganizationsPage() {
  const { orgId, setOrgId, handleOrgChange, handleProviderChange } = useAppContext()

  return (
    <>
      <OrganizationManager
        orgId={orgId}
        setOrgId={setOrgId}
        onOrgChange={handleOrgChange}
      />
      <ProviderManager orgId={orgId} onProviderChange={handleProviderChange} />
    </>
  )
}
