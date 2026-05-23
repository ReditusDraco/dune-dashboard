import { Link, useLocation } from 'react-router-dom'
import { useApp } from '../../stores/AppContext'
import ThemeSwitcher from './ThemeSwitcher'
import ConnectionBadge from './ConnectionBadge'

const NAV_ITEMS = [
  { path: '/', label: 'Overview' },
  { path: '/players', label: 'Players' },
  { path: '/guilds', label: 'Guilds' },
  { path: '/vehicles', label: 'Vehicles' },
  { path: '/buildings', label: 'Buildings' },
  { path: '/map', label: 'Map' },
  { path: '/accounts', label: 'Accounts' },
  { path: '/server', label: 'Server' },
  { path: '/chat', label: 'Chat' },
  { path: '/admin', label: 'Admin' },
  { path: '/files', label: 'Files' },
  { path: '/director', label: 'Director' },
  { path: '/settings', label: 'Settings' },
  { path: '/shell', label: 'Shell' },
]

export default function NavBar() {
  const location = useLocation()
  const { state } = useApp()

  return (
    <nav className="sticky top-0 z-50 h-[52px] bg-nav-bg flex items-center px-6 shadow-md border-b border-border">
      <div className="flex items-center gap-2 mr-8">
        <span className="text-primary font-serif font-bold text-lg tracking-wide">Dune</span>
        <span className="text-nav-text text-xs uppercase tracking-widest">Admin</span>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`px-4 h-[52px] flex items-center text-[13px] font-medium border-b-2 transition-colors whitespace-nowrap ${
              location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))
                ? 'text-nav-active border-nav-active'
                : 'text-nav-text border-transparent hover:text-white hover:bg-white/5'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-4">
        <ConnectionBadge />
        <ThemeSwitcher />
        {state.user && (
          <span className="text-nav-text text-xs">{state.user}</span>
        )}
      </div>
    </nav>
  )
}
