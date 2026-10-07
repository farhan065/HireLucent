import { BookOpen, BriefcaseBusiness, LayoutDashboard, LogOut, Sparkles } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext.js'
import Logo from '../components/Logo.jsx'

const NAV_ITEMS = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/jobs', label: 'Jobs', icon: BriefcaseBusiness },
  { to: '/app/assistant', label: 'AI Agent', icon: Sparkles },
  { to: '/app/knowledge', label: 'Knowledge Base', icon: BookOpen },
]

function navClass({ isActive }) {
  const base = 'flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-[15px] font-semibold'
  return isActive ? `${base} bg-tint text-brand-dark` : `${base} text-body hover:bg-mist`
}

// The signed-in interviewer and the sign-out button.
function UserPanel() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleSignOut() {
    navigate('/')
    logout()
  }

  return (
    <div className="flex items-center gap-3 rounded-2xl bg-mist p-3 md:mt-auto">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-navy">{user.full_name}</p>
        <p className="text-[13px] capitalize">{user.role}</p>
      </div>
      <button
        type="button"
        onClick={handleSignOut}
        className="flex min-h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-brand hover:bg-tint"
      >
        <LogOut className="size-4" aria-hidden="true" />
        Sign out
      </button>
    </div>
  )
}

// The interviewer workspace: navigation on the left, the current page on the right.
export default function AppLayout() {
  return (
    <div className="min-h-screen bg-mist md:flex">
      <aside className="flex flex-col gap-6 border-b border-line bg-white p-4 md:w-64 md:border-b-0 md:border-r md:px-4 md:py-6">
        <div className="px-2">
          <Logo to="/app" />
        </div>
        <nav aria-label="Workspace" className="flex gap-1.5 md:flex-col">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={navClass}>
              <Icon className="size-5" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <UserPanel />
      </aside>
      <main className="min-w-0 flex-1 p-6 md:p-10">
        <Outlet />
      </main>
    </div>
  )
}
