import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Home' },
  { to: '/organizations', label: 'Organizations' },
  { to: '/dashboards', label: 'Dashboards' },
  { to: '/monitors', label: 'Monitors' },
  { to: '/metrics', label: 'Metrics' },
]

export function Layout() {
  return (
    <div className="app">
      <header className="header">
        <h1>Metrics Explorer</h1>
        <nav className="nav-bar">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `nav-link${isActive ? ' nav-link--active' : ''}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
