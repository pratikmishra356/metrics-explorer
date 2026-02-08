import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppProvider } from './context/AppContext'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { OrganizationsPage } from './pages/OrganizationsPage'
import { DashboardsPage } from './pages/DashboardsPage'
import { MonitorsPage } from './pages/MonitorsPage'
import { MetricsPage } from './pages/MetricsPage'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="organizations" element={<OrganizationsPage />} />
            <Route path="dashboards" element={<DashboardsPage />} />
            <Route path="monitors" element={<MonitorsPage />} />
            <Route path="metrics" element={<MetricsPage />} />
          </Route>
        </Routes>
      </AppProvider>
    </BrowserRouter>
  )
}
