import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

const PROVIDER_OPTIONS = ['datadog', 'prometheus', 'grafana']

interface AppContextValue {
  orgId: string
  setOrgId: (v: string) => void
  selectedProvider: string
  setSelectedProvider: (v: string) => void
  providerOptions: string[]
  handleOrgChange: () => void
  handleProviderChange: () => void
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [orgId, setOrgId] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')

  const handleOrgChange = useCallback(() => {
    // Hook for future: refetch provider list, etc.
  }, [])

  const handleProviderChange = useCallback(() => {
    // Hook for future: refetch after adding a provider
  }, [])

  return (
    <AppContext.Provider
      value={{
        orgId,
        setOrgId,
        selectedProvider,
        setSelectedProvider,
        providerOptions: PROVIDER_OPTIONS,
        handleOrgChange,
        handleProviderChange,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useAppContext must be used within AppProvider')
  return ctx
}
